# Decisões técnicas e limitações

## 1. Resultado e escopo

Foram lidos 474 eventos de origem, referentes a 150 pedidos, e 137 linhas no destino. Cinco eventos de origem eram cópias exatas e foram removidos por idempotência, restando 469 eventos. O destino tem 133 IDs distintos; há uma cópia exata adicional do pedido 10002 e três IDs com múltiplas linhas conflitantes (10032, 10079 e 10127).

A reconstrução encontrou:
- 147 pedidos com um último estado unívoco;
- 17 desses pedidos terminam com operação `D` (exclusão);
- 130 pedidos ativos com estado final unívoco;
- 3 pedidos com empate conflitante no timestamp máximo (10054, 10105 e 10149);
- 30 pedidos com divergência confirmada;
- 6 casos não conclusivos, mantidos em `casos_nao_conclusivos.csv`.

A população esperada é de 133 pedidos ativos: 130 com estado final unívoco mais 3 com evento final empatado. O destino também possui 133 IDs distintos, mas a igualdade de contagem não significa igualdade de conteúdo.

## 2. Decisões tomadas

### Reconstrução do estado atual

**Decisão:** para cada `id_pedido`, selecionar o evento com maior `atualizado_em`, e não a última linha do arquivo.

**Motivo:** o enunciado informa que a ordem de chegada/gravação não é cronológica. O timestamp do evento é a única referência temporal disponível. A operação `D` no último evento significa que o pedido não deve existir no destino.

**Alternativas descartadas:** usar a ordem física do CSV; escolher o evento mais frequente; ou ordenar por operação (`I`, `U`, `D`). Nenhuma dessas regras tem suporte no contrato fornecido.

### Eventos repetidos

**Decisão:** remover somente eventos integralmente idênticos, considerando todas as colunas.

**Motivo:** uma entrega duplicada do mesmo evento não altera o estado. A deduplicação é idempotente e preserva eventos diferentes que compartilham o mesmo pedido e horário.

**Cuidado:** não deduplicar apenas por `id_pedido + timestamp`. Isso apagaria mudanças legítimas ou conflitos que precisam ser expostos.

### Empate no timestamp máximo da origem

**Decisão:** não escolher arbitrariamente uma versão para 10054, 10105 e 10149. Os três foram colocados em `casos_nao_conclusivos.csv` e não entram na comparação definitiva.

**Motivo:** em cada um há dois eventos distintos com o mesmo timestamp máximo e valores/status diferentes. Não existe sequência, número de versão, offset de origem ou identificador de evento para desempatar.

**Alternativas descartadas:** escolher a primeira ou a última linha do CSV (a ordem de chegada não é cronológica); escolher a versão que coincide com o destino (seria raciocínio circular); escolher o maior valor ou um status considerado “mais avançado” (regra de negócio inventada).

### Eventos sem criação (`I`)

**Decisão:** aceitar o último `U` como último estado observável, mas registrar a limitação.

**Motivo:** quatro pedidos não têm evento `I` no arquivo (10013, 10059, 10081 e 10103). O enunciado avisa que a captura pode ter começado depois da operação do sistema. O último `U` contém um snapshot de status e valor, então é útil para reconciliação pontual, mas não prova que o histórico esteja completo desde a criação.

### Operação de exclusão

**Decisão:** um pedido cujo último evento unívoco é `D` é considerado ausente da população ativa esperada. Se ainda existe no destino, é divergência.

**Motivo:** o destino deve conter apenas pedidos que existem atualmente na origem. `D` é a única evidência disponível de exclusão.

### Normalização de status

**Decisão:** comparar status após `strip()` e conversão para maiúsculas.

**Motivo:** `PAGO`, `pago` e ` PAGO ` representam a mesma categoria aparente; espaços e caixa não devem gerar falso positivo. O valor original continua preservado no CSV de divergências.

**Limitação:** não foi aplicada uma tabela de sinônimos nem tradução de status. Valores diferentes após essa normalização continuam divergentes.

### Interpretação dos timestamps

**Decisão:** converter os timestamps da origem para UTC respeitando o offset explícito `-03:00`; interpretar os timestamps sem fuso do destino como UTC.

**Evidência:** em muitos pedidos, a hora do destino é exatamente três horas posterior à hora de parede exibida na origem. Exemplo: origem `2026-05-12T21:37:00-03:00` e destino `2026-05-13 00:37:00`; representam o mesmo instante se o destino for UTC.

**Alternativa descartada:** comparar as strings ou os horários sem normalização. Isso marcaria incorretamente praticamente todos os pedidos como divergentes.

**Risco:** o CSV do destino não declara seu fuso. A hipótese de UTC é fortemente sugerida pelos pares observados, mas precisa ser confirmada com a equipe responsável pelo destino. Se o destino usar outro fuso, a classificação de timestamps deve ser recalculada.

### Valores monetários

**Decisão:** comparar com tolerância de meio centavo (`R$ 0,005`) para evitar divergência causada apenas por representação/arredondamento. Não converter valor nulo em zero e não carregar automaticamente o valor anterior.

**Motivo:** o enunciado não define se `NULL` significa “desconhecido”, “não alterado” ou “zero”. Fazer carry-forward ou preencher com zero inventaria uma regra.

**Casos:** 10064, 10098 e 10119 têm valor nulo no último evento da origem. Como o destino informa zero, não é possível afirmar que o destino está certo ou errado apenas com os arquivos. Foram mantidos como não conclusivos.

### Linhas duplicadas no destino

**Decisão:** remover cópias integralmente idênticas antes da comparação por pedido; não escolher entre linhas conflitantes. Para IDs com linhas diferentes, registrar `DESTINO_DUPLICADO_CONFLITANTE`.

**Motivo:** duplicata idêntica é repetição física sem diferença de estado. Já linhas com status/valor diferentes não têm critério temporal ou de versão que permita decidir qual é a correta.

**Impacto:** o pedido 10002 aparece duas vezes de forma idêntica. Isso não é divergência de estado, mas duplica o valor numa agregação simples sobre as 137 linhas. Os pedidos 10032, 10079 e 10127 possuem duplicidades conflitantes e foram reportados.

### Classificação e contagem

**Decisão:** uma linha por pedido divergente. Quando mais de um campo diverge, `tipo_divergencia` combina os nomes dos problemas com `+`. Casos de pedido ausente ou excluído recebem uma classificação própria.

**Motivo:** evita inflar a quantidade de pedidos divergentes quando vários campos do mesmo pedido estão errados. A contagem de 30 é por `id_pedido`, não por campo.

## 3. Casos sem resposta única

1. **Empates no último timestamp (10054, 10105, 10149):** não há sequência confiável entre eventos distintos com o mesmo instante. Sem `event_id`, sequência transacional ou log de commit, não é possível reconstruir um estado único.
2. **Valores nulos finais (10064, 10098, 10119):** o log não informa se nulo significa ausência de mudança, dado desconhecido ou valor efetivamente vazio. Não foi feito carry-forward.
3. **Fuso do destino:** a hipótese UTC explica o deslocamento de três horas nos pares correspondentes, mas o arquivo não carrega metadado de fuso. Precisa de confirmação operacional.
4. **Eventos ausentes e início tardio da captura:** o sistema não garante entrega e a captura pode ter começado depois da criação. O último evento disponível é o último estado observável, não uma prova matemática de estado atual da origem.
5. **Exclusões e recriações:** o arquivo não define se um pedido pode ser recriado com o mesmo `id_pedido` depois de `D`. A implementação trata o maior timestamp como estado final e não modela ciclos de vida separados.

## 4. Premissas assumidas

- `atualizado_em` representa o instante do evento, e não o horário em que o consumidor da fila recebeu o evento.
- O timestamp do destino sem offset está em UTC, conforme evidência dos pares comparáveis.
- `D` significa exclusão efetiva e o destino deve remover esse pedido.
- `id_pedido` é a chave de negócio estável entre sistemas.
- `id_cliente` deve ser idêntico nos dois sistemas; não há tabela de correspondência de clientes.
- `valor_total` é comparável diretamente entre os sistemas e está na mesma moeda.
- O destino deve refletir o último estado conhecido, inclusive status como `CANCELADO`; cancelamento não equivale à exclusão.
- Diferença menor que meio centavo é tratada como arredondamento, não como divergência material.

## 5. Impacto financeiro e interpretação

A soma bruta das 137 linhas do destino é R$ 308.232,91. Ao remover a linha exatamente duplicada do pedido 10002, a soma é R$ 306.320,32. A origem soma R$ 276.492,52 nos 130 pedidos ativos com estado final unívoco, considerando apenas valores conhecidos.

Os três pedidos com evento final empatado acrescentam entre R$ 13.296,65 e R$ 14.360,38, conforme a versão escolhida. Assim, o subtotal de origem conhecido, sem os três valores nulos, fica entre R$ 289.789,17 e R$ 290.852,90. Comparando com a soma bruta do destino, a diferença parcial fica entre R$ 17.380,01 e R$ 18.443,74, **antes** de considerar o valor desconhecido dos pedidos 10064, 10098 e 10119.

Portanto, não apresento um único número como diferença exata de faturamento. Para fechar esse número, é necessário resolver os três empates, recuperar os três valores nulos e confirmar a semântica do timestamp do destino. Também é importante definir se o relatório comercial agrega linhas físicas ou pedidos distintos, pois a cópia exata de 10002 duplica R$ 1.912,59 numa soma direta.

## 6. Limitações

- O log não garante entrega completa; eventos perdidos não podem ser inferidos apenas a partir dos arquivos.
- A solução não consulta a origem transacional ao vivo nem executa uma fotografia consistente (snapshot) dos dois sistemas.
- Não há `event_id`, sequência de transação, versão do registro ou watermark para desempate e detecção de lacunas.
- Não há regra formal para `NULL`, fuso do destino, moeda, arredondamento ou recriação após exclusão.
- A implementação usa pandas e carrega os dois CSVs em memória. Para volume 1.000 vezes maior, seria necessário processamento incremental/particionado ou engine distribuída, além de índices/chaves e persistência do estado.
- O script produz uma fotografia da reconciliação; não implementa monitoramento contínuo, alertas, retry, dead-letter queue ou correção automática.
- A classificação de `PEDIDO_EXCLUIDO_AINDA_NO_DESTINO` assume que `D` é a exclusão final. Se houver política de retenção no destino, essa regra precisaria ser revista.

## 7. O que eu faria com mais tempo

1. Confirmaria formalmente o fuso do destino e a semântica de `atualizado_em`.
2. Pediria ao time transacional um snapshot de referência ou endpoint para validar os casos ambíguos e os valores nulos.
3. Adicionaria `event_id`, sequência por pedido e timestamp de commit ao contrato do evento.
4. Criaria testes automatizados para eventos fora de ordem, duplicatas, empate de timestamp, exclusão, recriação, nulos e variação de status.
5. Mediria atraso e completude da captura com watermark e contagem de eventos por partição.
6. Separaria reconciliação de estado e reconciliação financeira, com regra formal sobre status faturáveis e agregação por pedido.

## 8. Uso de IA

Usei **ChatGPT (GPT-6)** como apoio para estruturar a abordagem, revisar as decisões de reconciliação, escrever e testar o script Python e redigir a documentação. Os arquivos CSV fornecidos foram usados como base da análise. As decisões finais, premissas, limitações e números apresentados precisam ser compreendidos e defendidos por mim na entrevista; não devo afirmar como fato nenhuma hipótese que ainda depende de confirmação, especialmente o fuso do destino e a semântica dos valores nulos.
