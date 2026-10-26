"""Analisa os resultados do experimento ATLAS e gera tabelas e gráficos.

Uso no terminal do VS Code (na pasta deste arquivo):
    python -m pip install -r requirements.txt
    python analisar_resultados.py

Os arquivos gerados ficam em ./resultados_analise/.
"""

from pathlib import Path
import re

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
ARQUIVO = ROOT / "Execucoes_organizadas_M1_M2_M3_v2.xlsx"
SAIDA = ROOT / "resultados_analise"
ABA_EXECUCOES = 0

COLUNAS = {
    "ID da execução": "execucao",
    "Modelo": "modelo",
    "Código": "codigo",
    "Repetição": "repeticao",
    "Problemas detectados": "problemas_detectados",
    "VP": "vp",
    "FP": "fp",
    "FN": "fn",
}

ORDEM_MODELOS = [
    "M1 – gemma-4-E4B-it-GGUF",
    "M2 – Qwen3.6-27B-GGUF",
    "M3 – GPT-5.6 Luna",
]


def razao(numerador, denominador):
    return numerador / denominador if denominador else float("nan")


def calcular_metricas(linhas, grupos):
    """Soma as contagens antes de calcular as métricas, como define o plano."""
    agrupado = linhas.groupby(grupos, dropna=False, as_index=False).agg(
        vp=("vp", "sum"), fp=("fp", "sum"), fn=("fn", "sum"),
        n_execucoes=("execucao", "count"),
    )
    agrupado["precisao"] = [razao(vp, vp + fp) for vp, fp in zip(agrupado.vp, agrupado.fp)]
    agrupado["revocacao"] = [razao(vp, vp + fn) for vp, fn in zip(agrupado.vp, agrupado.fn)]
    agrupado["f1"] = [razao(2 * vp, 2 * vp + fp + fn) for vp, fp, fn in zip(agrupado.vp, agrupado.fp, agrupado.fn)]
    return agrupado


def carregar_dados():
    if not ARQUIVO.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {ARQUIVO}")
    dados = pd.read_excel(ARQUIVO, sheet_name=ABA_EXECUCOES)
    dados = dados.rename(columns=COLUNAS)
    faltantes = set(COLUNAS.values()) - set(dados.columns)
    if faltantes:
        raise ValueError(f"Colunas ausentes na aba de execuções: {sorted(faltantes)}")
    for col in ["repeticao", "vp", "fp", "fn"]:
        dados[col] = pd.to_numeric(dados[col], errors="coerce")
    dados["modelo"] = (dados.modelo.astype(str)
                       .str.replace("—", "–", regex=False)
                       .str.replace("�", "–", regex=False))
    dados["modelo"] = dados.modelo.replace({"M1 – gemma-4-E4B-it-GGUF": ORDEM_MODELOS[0],
                                            "M2 – Qwen3.6-27B-GGUF": ORDEM_MODELOS[1],
                                            "M3 – GPT-5.6 Luna": ORDEM_MODELOS[2]})
    dados["cenario"] = dados.codigo.astype(str).str.extract(r"^(C\d+)", expand=False)
    dados["problemas_detectados"] = dados.problemas_detectados.fillna("").astype(str)
    dados["ids_detectados"] = dados.problemas_detectados.apply(
        lambda valor: [x.strip() for x in re.split(r"[;,]", valor)
                       if x.strip() and x.strip() not in {"–", "—", "-", "nan"}]
    )
    return dados


def validar(dados):
    chaves = ["modelo", "codigo", "repeticao"]
    duplicatas = dados[dados.duplicated(chaves, keep=False)].sort_values(chaves)
    inconsistencias = []
    for _, linha in dados.iterrows():
        if pd.isna(linha.vp) or pd.isna(linha.fp) or pd.isna(linha.fn):
            inconsistencias.append(f"{linha.execucao}: VP/FP/FN incompleto")
        elif len(linha.ids_detectados) != int(linha.vp):
            inconsistencias.append(
                f"{linha.execucao}: VP={int(linha.vp)}, mas há {len(linha.ids_detectados)} IDs detectados"
            )
        elif len(set(linha.ids_detectados)) != len(linha.ids_detectados):
            inconsistencias.append(f"{linha.execucao}: há ID de problema repetido na lista de detecções")
    dados_com_total = dados.assign(total_esperado=dados.vp + dados.fn)
    totais = dados_com_total.groupby("codigo").total_esperado.nunique(dropna=True)
    for codigo, quantidade in totais.items():
        if quantidade != 1:
            inconsistencias.append(f"{codigo}: total de problemas esperados varia entre execuções")
    combinacoes = dados.groupby(["modelo", "repeticao"]).codigo.nunique()
    rodadas_completas = combinacoes[combinacoes == 10]
    return duplicatas, inconsistencias, rodadas_completas


def preparar_graficos(dados, repeticoes, por_codigo, frequencias):
    sns.set_theme(style="whitegrid", context="talk", palette="colorblind")

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.pointplot(data=repeticoes, x="modelo", y="f1", errorbar="sd", capsize=0.12,
                  order=ORDEM_MODELOS, ax=ax)
    ax.set(title="F1 por modelo — média das repetições completas",
           xlabel="Modelo", ylabel="F1 (média ± desvio padrão amostral)", ylim=(0, 1))
    ax.tick_params(axis="x", rotation=12)
    fig.tight_layout()
    fig.savefig(SAIDA / "f1_por_modelo.png", dpi=180)
    plt.close(fig)

    # Acertos por execução: cada VP equivale a um ID de problema esperado identificado.
    codigos = sorted(dados.codigo.unique())
    esperados = (dados.assign(esperados=dados.vp + dados.fn)
                 .groupby("codigo").esperados.first().astype(int))
    dados_grafico = dados.copy()
    dados_grafico["codigo_rotulo"] = dados_grafico.codigo.map(
        lambda codigo: f"{codigo}\n({esperados[codigo]} esperados)"
    )
    ordem_rotulos = [f"{codigo}\n({esperados[codigo]} esperados)" for codigo in codigos]
    fig, ax = plt.subplots(figsize=(15, 7))
    sns.barplot(data=dados_grafico, x="codigo_rotulo", y="vp", hue="modelo",
                hue_order=ORDEM_MODELOS, order=ordem_rotulos, errorbar="sd",
                capsize=.08, ax=ax)
    ax.set(title="Erros esperados identificados por código",
           xlabel="Código (quantidade de erros esperados)",
           ylabel="Média de acertos por execução (barras: desvio padrão)")
    ax.set_ylim(0, int(esperados.max()) + .5)
    ax.legend(title="Modelo", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(SAIDA / "acertos_por_codigo.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=por_codigo, x="codigo", y="f1", hue="modelo", hue_order=ORDEM_MODELOS, ax=ax)
    ax.set(title="F1 por código de teste (contagens somadas nas cinco repetições)",
           xlabel="Código", ylabel="F1", ylim=(0, 1))
    ax.legend(title="Modelo", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(SAIDA / "f1_por_codigo.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(19, 9), sharey=True)
    for ax, modelo in zip(axes, ORDEM_MODELOS):
        quadro = frequencias[frequencias.modelo == modelo].pivot(
            index="problema", columns="modelo", values="frequencia"
        )
        # Mantém as 24 linhas para facilitar a comparação entre modelos.
        sns.heatmap(quadro, vmin=0, vmax=1, cmap="crest", annot=True, fmt=".0%",
                    linewidths=.4, cbar=(modelo == ORDEM_MODELOS[-1]), ax=ax)
        ax.set(title=modelo, xlabel="", ylabel="Problema esperado" if ax is axes[0] else "")
    fig.suptitle("Frequência de detecção de cada problema (repetições avaliadas)", y=1.01)
    fig.tight_layout()
    fig.savefig(SAIDA / "frequencia_por_problema.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    SAIDA.mkdir(exist_ok=True)
    dados = carregar_dados()
    duplicatas, inconsistencias, rodadas_completas = validar(dados)

    validas = dados.drop(index=duplicatas.index).copy()
    validas = validas[validas[["vp", "fp", "fn"]].notna().all(axis=1)]
    por_repeticao = calcular_metricas(validas, ["modelo", "repeticao"])
    por_modelo = por_repeticao.groupby("modelo", as_index=False).agg(
        f1_media=("f1", "mean"), f1_dp=("f1", "std"),
        precisao_media=("precisao", "mean"), revocacao_media=("revocacao", "mean"),
        rodadas_completas=("f1", "count"),
    )
    por_codigo = calcular_metricas(validas, ["modelo", "codigo", "cenario"])
    acertos_codigo = validas.groupby(["modelo", "codigo"], as_index=False).agg(
        acertos_total=("vp", "sum"), acertos_medios=("vp", "mean"),
        variacao_acertos=("vp", "std"), repeticoes_avaliadas=("vp", "count"),
        fp_total=("fp", "sum"), fn_total=("fn", "sum"),
    )
    esperados_codigo = (validas.assign(erros_esperados=validas.vp + validas.fn)
                        .groupby("codigo").erros_esperados.first())
    acertos_codigo["erros_esperados_por_execucao"] = acertos_codigo.codigo.map(esperados_codigo)
    acertos_codigo["acertos_possiveis_total"] = (
        acertos_codigo.erros_esperados_por_execucao * acertos_codigo.repeticoes_avaliadas
    )
    acertos_codigo["revocacao_agregada"] = (
        acertos_codigo.acertos_total / acertos_codigo.acertos_possiveis_total
    )
    maximos = acertos_codigo.groupby("codigo").acertos_medios.transform("max")
    acertos_codigo["lidera_codigo"] = acertos_codigo.acertos_medios.eq(maximos)
    vencedores = (acertos_codigo[acertos_codigo.lidera_codigo]
                  .groupby("codigo", as_index=False)
                  .agg(modelos_com_mais_acertos=("modelo", lambda serie: "; ".join(serie)),
                       maior_media_acertos=("acertos_medios", "first"),
                       maior_total_acertos=("acertos_total", "first"),
                       repeticoes_avaliadas=("repeticoes_avaliadas", "first"),
                       erros_esperados_por_execucao=("erros_esperados_por_execucao", "first")))
    vencedores["acertos_possiveis_total"] = (
        vencedores.erros_esperados_por_execucao * vencedores.repeticoes_avaliadas
    )
    por_cenario_repeticao = calcular_metricas(validas, ["modelo", "repeticao", "cenario"])
    por_cenario = por_cenario_repeticao.groupby(["modelo", "cenario"], as_index=False).agg(
        f1_media=("f1", "mean"), f1_dp=("f1", "std"),
        precisao_media=("precisao", "mean"), revocacao_media=("revocacao", "mean"),
    )

    problema_longo = validas[["modelo", "codigo", "repeticao", "ids_detectados"]].explode("ids_detectados")
    detectados = problema_longo.dropna(subset=["ids_detectados"]).rename(columns={"ids_detectados": "problema"})
    # O inventário é construído a partir dos IDs encontrados e inclui sua frequência por modelo.
    denominadores = validas.groupby(["modelo", "codigo"]).size().rename("execucoes_avaliadas")
    contagens = detectados.groupby(["modelo", "codigo", "problema"]).repeticao.count().rename("deteccoes")
    freq = contagens.to_frame().join(denominadores, on=["modelo", "codigo"]).reset_index()
    freq["frequencia"] = freq.deteccoes / freq.execucoes_avaliadas
    # Acrescenta problemas que nunca foram detectados, inferindo a lista esperada dos IDs existentes no conjunto.
    inventario = sorted({f"{codigo}-{i:02d}" for codigo in validas.codigo.unique()
                         for i in range(1, int((validas[validas.codigo == codigo].vp + validas[validas.codigo == codigo].fn).max()) + 1)})
    todos = pd.MultiIndex.from_product([ORDEM_MODELOS, validas.codigo.drop_duplicates().sort_values(), inventario],
                                       names=["modelo", "codigo", "problema"]).to_frame(index=False)
    todos = todos[todos.apply(lambda r: r.problema.startswith(r.codigo + "-"), axis=1)]
    freq = todos.merge(freq, on=["modelo", "codigo", "problema"], how="left")
    freq = freq.merge(validas.groupby(["modelo", "codigo"]).size().rename("execucoes_no_codigo").reset_index(),
                      on=["modelo", "codigo"], how="left")
    freq["deteccoes"] = freq.deteccoes.fillna(0).astype(int)
    freq["execucoes_avaliadas"] = freq.execucoes_avaliadas.fillna(freq.execucoes_no_codigo).fillna(0).astype(int)
    freq["frequencia"] = freq.deteccoes.div(freq.execucoes_avaliadas.where(freq.execucoes_avaliadas != 0))

    por_modelo.to_csv(SAIDA / "metricas_por_modelo.csv", index=False, encoding="utf-8-sig")
    por_repeticao.to_csv(SAIDA / "metricas_por_repeticao.csv", index=False, encoding="utf-8-sig")
    por_codigo.to_csv(SAIDA / "metricas_por_codigo.csv", index=False, encoding="utf-8-sig")
    por_cenario.to_csv(SAIDA / "metricas_por_cenario.csv", index=False, encoding="utf-8-sig")
    acertos_codigo.to_csv(SAIDA / "acertos_por_codigo.csv", index=False, encoding="utf-8-sig")
    vencedores.to_csv(SAIDA / "vencedores_por_codigo.csv", index=False, encoding="utf-8-sig")
    freq.to_csv(SAIDA / "frequencia_por_problema.csv", index=False, encoding="utf-8-sig")
    preparar_graficos(validas, por_repeticao, por_codigo, freq.dropna(subset=["frequencia"]))

    resumo = ["# Análise dos resultados do experimento ATLAS", "",
              f"Planilha analisada: `{ARQUIVO.name}`", "",
              f"Registros: {len(dados)}. Rodadas completas por modelo e repetição: {len(rodadas_completas)}.",
              f"Registros duplicados (modelo, código, repetição): {len(duplicatas)}.",
              f"Inconsistências encontradas: {len(inconsistencias)}.", "",
              "## Comparação dos modelos", "",
              "Métricas calculadas somando VP, FP e FN dentro de cada repetição completa; depois, média e desvio padrão entre repetições.", "",
              "| Modelo | Precisão média | Revocação média | F1 médio ± DP | Rodadas |",
              "|---|---:|---:|---:|---:|"]
    for _, r in por_modelo.iterrows():
        resumo.append(f"| {r.modelo} | {r.precisao_media:.3f} | {r.revocacao_media:.3f} | {r.f1_media:.3f} ± {r.f1_dp:.3f} | {int(r.rodadas_completas)} |")
    resumo += ["", "## Observações metodológicas", "",
               "- O F1 agregado usa `2 × VP / (2 × VP + FP + FN)`, conforme o plano de avaliação.",
               "- As cinco repetições são descritas; não se afirma significância estatística nem superioridade universal.",
               "- Os códigos e cenários são uma amostra experimental construída; as conclusões se limitam às condições avaliadas.",
               "- A frequência por problema informa em quantas execuções avaliadas cada ID foi detectado.",
               "- Para o líder de cada código, compara-se a média de VP por execução; empates são mantidos.", "",
               "## Modelo com mais acertos por código", "",
               "Os acertos são os IDs de problemas esperados identificados. O máximo possível depende do código; a comparação usa a média de VP por execução e considera todas as repetições avaliadas.", "",
               "| Código | Erros esperados por execução | Modelo(s) com mais acertos | Média de acertos por execução |",
               "|---|---:|---|---:|"]
    for _, r in vencedores.iterrows():
        resumo.append(f"| {r.codigo} | {int(r.erros_esperados_por_execucao)} | {r.modelos_com_mais_acertos} | {r.maior_media_acertos:.2f} |")
    resumo += ["", "## Gráficos", "",
               "![Acertos por código](acertos_por_codigo.png)", "",
               "![F1 por modelo](f1_por_modelo.png)", "",
               "![F1 por código](f1_por_codigo.png)", "",
               "![Frequência por problema](frequencia_por_problema.png)", ""]
    if inconsistencias:
        resumo += ["## Inconsistências", ""] + [f"- {item}" for item in inconsistencias]
    (SAIDA / "relatorio.md").write_text("\n".join(resumo), encoding="utf-8")
    print(f"Análise concluída. Resultados em: {SAIDA}")
    print(por_modelo.to_string(index=False))


if __name__ == "__main__":
    main()
