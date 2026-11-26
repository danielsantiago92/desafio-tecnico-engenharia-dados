#!/usr/bin/env python3
"""
Reconciliação de pedidos: reconstrói o último estado observável no log e compara
com a tabela analítica.

Uso:
    python reconciliar.py pedidos_origem.csv pedidos_destino.csv

Os CSVs devem estar no diretório atual ou ser informados por caminho.
Saídas:
    relatorio_divergencias.csv
    casos_nao_conclusivos.csv
    metricas_execucao.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

COLUNAS_ORIGEM = {
    "id_pedido", "id_cliente", "status", "valor_total",
    "atualizado_em", "operacao"
}
COLUNAS_DESTINO = {
    "id_pedido", "id_cliente", "status", "valor_total", "atualizado_em"
}
TOLERANCIA_VALOR = 0.005  # tolera diferença menor que meio centavo por arredondamento


def carregar_csv(caminho: Path, obrigatorias: set[str]) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    faltantes = obrigatorias - set(df.columns)
    if faltantes:
        raise ValueError(f"{caminho}: colunas ausentes: {sorted(faltantes)}")
    return df


def normalizar_status(valor) -> str:
    """Remove espaços periféricos e ignora caixa; não altera o valor original."""
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()


def normalizar_timestamp_origem(serie: pd.Series) -> pd.Series:
    # A origem fornece timestamps com offset explícito.
    return pd.to_datetime(serie, errors="coerce", utc=True)


def normalizar_timestamp_destino(serie: pd.Series) -> pd.Series:
    # Os timestamps do destino são naive. A evidência nos registros comuns
    # indica que representam UTC (e não horário local): origem -03:00 + 3h
    # coincide com destino. A hipótese é explícita e deve ser validada com o time.
    return pd.to_datetime(serie, errors="coerce", utc=True)


def json_registro(registro, colunas: list[str]) -> str:
    if registro is None:
        return ""
    if isinstance(registro, list):
        obj = [{c: (None if pd.isna(r[c]) else r[c]) for c in colunas} for r in registro]
    else:
        obj = {c: (None if pd.isna(registro[c]) else registro[c]) for c in colunas}
    return json.dumps(obj, ensure_ascii=False, default=str)


def reconstruir_estado(origem: pd.DataFrame):
    df = origem.copy()
    df["id_pedido"] = pd.to_numeric(df["id_pedido"], errors="raise").astype("int64")
    df["ts_utc"] = normalizar_timestamp_origem(df["atualizado_em"])
    if df["ts_utc"].isna().any():
        raise ValueError("Há timestamps inválidos na origem.")

    # Eventos exatamente repetidos são idempotentes: removê-los não muda estado.
    df = df.drop_duplicates(
        subset=["id_pedido", "id_cliente", "status", "valor_total",
                "atualizado_em", "operacao"]
    )

    # Não ordenar pelo índice/ordem de chegada: a fila não garante cronologia.
    maior_ts = df.groupby("id_pedido")["ts_utc"].transform("max")
    ultimos = df.loc[df["ts_utc"].eq(maior_ts)].copy()

    estados = []
    inconclusivos = []
    for pedido, grupo in ultimos.groupby("id_pedido", sort=True):
        # Mais de um conteúdo distinto no timestamp máximo: não há desempate
        # justificável com os campos disponíveis.
        distintos = grupo[
            ["id_cliente", "status", "valor_total", "operacao", "atualizado_em", "ts_utc"]
        ].drop_duplicates()
        if len(distintos) > 1:
            inconclusivos.append({
                "id_pedido": int(pedido),
                "motivo": "EVENTOS_FINAIS_CONFLITANTES_MESMO_TIMESTAMP",
                "valor_origem": json_registro(
                    grupo.to_dict("records"),
                    ["id_cliente", "status", "valor_total", "atualizado_em", "operacao"]
                ),
                "valor_destino": ""
            })
            continue
        estados.append(distintos.iloc[0].to_dict() | {"id_pedido": int(pedido)})

    return pd.DataFrame(estados), inconclusivos, df


def reconciliar(origem: pd.DataFrame, destino: pd.DataFrame):
    estado, inconclusivos, eventos = reconstruir_estado(origem)
    dest = destino.copy()
    dest["id_pedido"] = pd.to_numeric(dest["id_pedido"], errors="raise").astype("int64")
    dest["ts_utc"] = normalizar_timestamp_destino(dest["atualizado_em"])
    if dest["ts_utc"].isna().any():
        raise ValueError("Há timestamps inválidos no destino.")

    colunas = ["id_cliente", "status", "valor_total", "atualizado_em"]
    divergencias = []

    def adicionar(pedido, tipo, origem_reg=None, destino_reg=None, detalhe=""):
        divergencias.append({
            "id_pedido": int(pedido),
            "tipo_divergencia": tipo,
            "valor_origem": json_registro(origem_reg, colunas + (["operacao"] if origem_reg is not None and "operacao" in origem_reg else [])),
            "valor_destino": json_registro(destino_reg, colunas),
            "detalhe": detalhe
        })

    # Remove somente cópias idênticas do destino. Linhas conflitantes não podem
    # ser escolhidas arbitrariamente: são registradas como divergência própria.
    dest_sem_repeticao = dest.drop_duplicates(subset=list(COLUNAS_DESTINO))
    grupos_destino = {
        int(p): g for p, g in dest_sem_repeticao.groupby("id_pedido", sort=True)
    }
    ids_ambig_origem = {x["id_pedido"] for x in inconclusivos}

    for _, estado_pedido in estado.sort_values("id_pedido").iterrows():
        pedido = int(estado_pedido["id_pedido"])
        if estado_pedido["operacao"] == "D":
            continue
        grupo_dest = grupos_destino.get(pedido)
        if grupo_dest is None:
            adicionar(pedido, "PEDIDO_AUSENTE_NO_DESTINO", estado_pedido.to_dict(), None,
                      "Pedido ativo no último evento observado, sem linha no destino.")
            continue
        if len(grupo_dest) > 1:
            adicionar(pedido, "DESTINO_DUPLICADO_CONFLITANTE", estado_pedido.to_dict(),
                      grupo_dest.to_dict("records"),
                      "Há múltiplas linhas distintas para o mesmo pedido no destino.")
            continue

        d = grupo_dest.iloc[0]
        problemas = []
        if int(estado_pedido["id_cliente"]) != int(d["id_cliente"]):
            problemas.append("ID_CLIENTE_DIVERGENTE")
        if normalizar_status(estado_pedido["status"]) != normalizar_status(d["status"]):
            problemas.append("STATUS_DIVERGENTE")

        valor_origem_nulo = pd.isna(estado_pedido["valor_total"])
        if valor_origem_nulo:
            # Não converter NULL em zero nem carregar valor antigo sem regra
            # de negócio explícita.
            inconclusivos.append({
                "id_pedido": pedido,
                "motivo": "VALOR_TOTAL_NULO_NO_ULTIMO_EVENTO_DA_ORIGEM",
                "valor_origem": json_registro(estado_pedido.to_dict(), colunas + ["operacao"]),
                "valor_destino": json_registro(d.to_dict(), colunas)
            })
        elif abs(float(estado_pedido["valor_total"]) - float(d["valor_total"])) > TOLERANCIA_VALOR:
            problemas.append("VALOR_DIVERGENTE")

        if estado_pedido["ts_utc"] != d["ts_utc"]:
            problemas.append("DATA_ATUALIZACAO_DIVERGENTE")

        if problemas:
            adicionar(pedido, "+".join(problemas), estado_pedido.to_dict(), d.to_dict(),
                      "Campos comparados após normalização de status e timestamp.")

    # Linhas do destino sem pedido ativo conhecido na origem: podem ser pedidos
    # excluídos (D) ou sobras sem qualquer estado correspondente.
    ids_ativos_conhecidos = set(
        estado.loc[estado["operacao"] != "D", "id_pedido"].astype(int)
    )
    ids_excluidos = set(
        estado.loc[estado["operacao"] == "D", "id_pedido"].astype(int)
    )
    for pedido, grupo in grupos_destino.items():
        if pedido in ids_ativos_conhecidos or pedido in ids_ambig_origem:
            continue
        if pedido in ids_excluidos:
            adicionar(pedido, "PEDIDO_EXCLUIDO_AINDA_NO_DESTINO", None,
                      grupo.to_dict("records") if len(grupo) > 1 else grupo.iloc[0].to_dict(),
                      "O último evento observado na origem é D, mas o destino mantém o pedido.")
        else:
            adicionar(pedido, "PEDIDO_SEM_REGISTRO_NA_ORIGEM", None,
                      grupo.to_dict("records") if len(grupo) > 1 else grupo.iloc[0].to_dict(),
                      "O destino contém pedido sem identificador correspondente no log.")

    return pd.DataFrame(divergencias), pd.DataFrame(inconclusivos), estado, dest_sem_repeticao, eventos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origem", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--saida", type=Path, default=Path("."))
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    origem = carregar_csv(args.origem, COLUNAS_ORIGEM)
    destino = carregar_csv(args.destino, COLUNAS_DESTINO)
    div, inc, estado, dest_norm, eventos = reconciliar(origem, destino)

    div.to_csv(args.saida / "relatorio_divergencias.csv", index=False, encoding="utf-8-sig")
    inc.to_csv(args.saida / "casos_nao_conclusivos.csv", index=False, encoding="utf-8-sig")

    ativos = estado[estado["operacao"] != "D"]
    metricas = {
        "eventos_origem_lidos": int(len(origem)),
        "eventos_origem_apos_deduplicacao_exata": int(len(eventos)),
        "pedidos_distintos_no_log": int(origem["id_pedido"].nunique()),
        "pedidos_com_estado_final_univoco": int(len(estado)),
        "pedidos_ativos_com_estado_final_univoco": int(len(ativos)),
        "pedidos_com_ultimo_evento_D": int((estado["operacao"] == "D").sum()),
        "pedidos_com_eventos_finais_conflitantes": int(
            inc["motivo"].eq("EVENTOS_FINAIS_CONFLITANTES_MESMO_TIMESTAMP").sum()
        ) if not inc.empty else 0,
        "linhas_destino": int(len(destino)),
        "soma_destino_bruta_todas_as_linhas": round(float(destino["valor_total"].sum()), 2),
        "soma_destino_apos_remover_copias_exatas": round(float(dest_norm["valor_total"].sum()), 2),
        "pedidos_distintos_destino_apos_deduplicacao_exata": int(dest_norm["id_pedido"].nunique()),
        "divergencias_confirmadas": int(len(div)),
        "casos_nao_conclusivos": int(len(inc)),
        "valor_total_origem_conhecido_ativos_sem_ambiguidades": round(
            float(ativos["valor_total"].sum(skipna=True)), 2
        ),
        "valor_total_destino_linhas_apos_deduplicacao_exata": round(
            float(dest_norm["valor_total"].sum()), 2
        )
    }
    (args.saida / "metricas_execucao.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metricas, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
