# Análise dos resultados no Python e VS Code

O arquivo `analisar_resultados.py` lê a aba de execuções da planilha original, confere registros repetidos e consistência dos identificadores, recalcula as métricas pelas contagens de VP/FP/FN e cria tabelas e gráficos com Seaborn.

## Como executar no VS Code

1. Abra esta pasta no VS Code.
2. Abra o terminal integrado (`Terminal > Novo Terminal`).
3. Instale as dependências uma vez:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Execute a análise:

   ```powershell
   python analisar_resultados.py
   ```

O script espera que a planilha `Execucoes_organizadas_M1_M2_M3_v2.xlsx` permaneça nesta mesma pasta. As tabelas CSV, gráficos PNG e o relatório automático serão gravados em `resultados_analise/`.

## Arquivos gerados

- `metricas_por_modelo.csv`: média das métricas entre repetições completas.
- `metricas_por_repeticao.csv`: contagens e métricas para cada repetição.
- `metricas_por_codigo.csv`: comparação por código de teste.
- `metricas_por_cenario.csv`: comparação por tipo de problema (cenários C1 a C5).
- `acertos_por_codigo.csv`: VP total e média de acertos por código e modelo.
- `vencedores_por_codigo.csv`: modelo(s) com maior média de acertos em cada código; empates são mantidos.
- `frequencia_por_problema.csv`: frequência de identificação de cada problema previsto.
- `acertos_por_codigo.png`: média de problemas identificados em cada execução. O rótulo de cada código mostra quantos problemas eram esperados; as barras de erro mostram a variação entre repetições.
- `f1_por_modelo.png`, `f1_por_codigo.png` e `frequencia_por_problema.png`.
- `relatorio.md`: resumo automático com os resultados e os gráficos.

Cada ID em `Problemas detectados` representa um erro previsto identificado; o número de IDs deve corresponder ao VP da linha. Para responder qual modelo acertou mais em cada código, o script calcula a média de VP por execução ao longo das repetições e registra todos os modelos empatados na liderança. O máximo de erros esperados pode variar por código, por isso o gráfico informa essa quantidade no eixo horizontal.

O F1 é calculado como `2 × VP / (2 × VP + FP + FN)`. O script agrega as contagens em cada repetição antes de calcular as métricas, conforme o plano experimental. A precisão fica indefinida quando VP + FP = 0. Os resultados descrevem somente os códigos, modelos e configurações avaliados.
