# Reconciliação de Pedidos — Desafio Técnico de Engenharia de Dados

## Sobre o projeto

Este projeto tem como objetivo reconstruir o estado atual dos pedidos a partir de um histórico de eventos e comparar o resultado com uma tabela de destino utilizada para análise.

A origem contém eventos de inserção (I), atualização (U) e exclusão (D), que podem chegar fora de ordem e apresentar duplicidades.

O processo identifica divergências entre a origem e o destino, separando os casos em que é possível chegar a uma conclusão segura daqueles que exigem análise adicional.

## Tecnologias utilizadas

- Python 3.10+
- Pandas
- CSV
- JSON

## Estrutura do projeto

```text
case_tecnico/
├── pedidos_origem.csv
├── pedidos_destino.csv
├── reconciliar.py
├── requirements.txt
├── README.md
├── DECISOES.md
├── RESUMO.md
├── relatorio_divergencias.csv
├── casos_nao_conclusivos.csv
└── metricas_execucao.json
```

## Requisitos

- Python 3.10 ou superior
- pip

## Como executar

### 1. Clonar o repositório

```bash
git clone URL_DO_SEU_REPOSITORIO
```

### 2. Entrar na pasta do projeto

```bash
cd NOME_DO_REPOSITORIO
```

### 3. Criar um ambiente virtual

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Executar a reconciliação

```bash
python reconciliar.py pedidos_origem.csv pedidos_destino.csv --saida .
```

## Arquivos gerados

Após a execução, o programa gera:

- **relatorio_divergencias.csv:** divergências confirmadas entre a origem reconstruída e o destino.
- **casos_nao_conclusivos.csv:** situações em que não é possível determinar um estado final com segurança.
- **metricas_execucao.json:** métricas gerais da execução.

## Regras de negócio e decisões técnicas

- A reconstrução considera o maior timestamp de cada pedido.
- A ordem física das linhas do CSV não é utilizada como critério de ordenação dos eventos.
- Duplicidades exatas são tratadas antes da comparação.
- Empates conflitantes no timestamp mais recente são classificados como casos não conclusivos.
- Eventos de exclusão são considerados na reconstrução do estado.
- Os critérios, premissas e limitações estão detalhados em `DECISOES.md`.

## Resultados

Na execução de referência deste conjunto de dados, foram identificadas:

- 30 divergências confirmadas.
- 6 casos não conclusivos.

Os resultados podem variar se os arquivos de entrada forem alterados.

## Documentação complementar

- `DECISOES.md`: premissas, critérios técnicos, ambiguidades e limitações.
- `RESUMO.md`: resumo executivo dos resultados.

## Observação

Este projeto foi desenvolvido como solução para um desafio técnico de Engenharia de Dados. A implementação prioriza rastreabilidade, tratamento de eventos fora de ordem e transparência na classificação de casos ambíguos.