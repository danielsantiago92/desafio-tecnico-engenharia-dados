# Resumo executivo — Reconciliação de pedidos

A análise encontrou **30 pedidos com divergências confirmadas**, dentro de uma população esperada de **133 pedidos ativos**. Outros **6 pedidos ficaram sem conclusão segura**: em 3 casos o último evento da origem tem duas versões diferentes no mesmo horário; em outros 3, o valor mais recente da origem está vazio. Esses casos foram separados para não gerar acusações incorretas.

As divergências confirmadas se distribuem assim:

- 5 pedidos ativos não aparecem no relatório.
- 5 pedidos excluídos na origem continuam no destino.
- 3 pedidos têm mais de uma linha conflitante no destino.
- 3 pedidos têm cliente diferente.
- 4 têm status diferente (há combinações com outros campos).
- 7 têm valor diferente (há combinações com outros campos).
- 10 têm data de atualização diferente (há combinações com outros campos).

As categorias acima se sobrepõem quando um pedido apresenta mais de um campo errado; por isso, a soma dos números por campo é maior que os 30 pedidos divergentes.

**Impacto financeiro:** a soma bruta das 137 linhas do destino é **R$ 308.232,91**. Removendo uma cópia exatamente repetida, a soma cai para **R$ 306.320,32**. Na origem, os pedidos ativos com valor conhecido e estado final sem ambiguidade somam **R$ 276.492,52**. Há ainda 3 pedidos com empate de eventos finais: dependendo da versão escolhida, acrescentam entre **R$ 13.296,65 e R$ 14.360,38**. Assim, a diferença observável entre a soma bruta do destino e o subtotal conhecido da origem fica entre **R$ 17.380,01 e R$ 18.443,74**, antes de considerar os valores desconhecidos de 3 pedidos cujo valor final está nulo. Portanto, **não é tecnicamente correto apresentar esse intervalo como diferença final exata de faturamento**.

Eu resolveria primeiro a integridade da população: reinserir os 5 pedidos ativos ausentes e retirar os 5 pedidos cujo último evento é exclusão. Em paralelo, corrigiria as 3 duplicidades conflitantes do destino. Esses casos alteram diretamente a quantidade de pedidos e podem distorcer o faturamento; depois disso, trataria os valores divergentes, os status e o contrato de timestamps.
