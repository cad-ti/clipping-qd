#!/usr/bin/env python3
import csv
import os
import yaml
import glob
import logging
import requests
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EMAIL_REMETENTE = os.environ.get("EMAIL_REMETENTE") 
EMAIL_SENHA = os.environ.get("EMAIL_SENHA")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True
)
logger = logging.getLogger(__name__)

ontem = date.today() - timedelta(days=1)
ontem_fmt_iso8601 = ontem.strftime("%Y-%m-%d")
ontem_fmt_br = ontem.strftime("%d/%m/%Y")

def carregar_codigos_ibge():
    codigos = []
    with open("dados/municipios_rj.csv", newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            codigos.append(row["codigo_ibge"])
    return codigos
CODIGOS_IBGE_RJ = carregar_codigos_ibge()

def buscar_termo_no_querido_diario(termo):
    # DOC API: https://queridodiario.ok.org.br/api/docs#/default/Search_for_content_in_gazettes_gazettes_get
    url = "https://queridodiario.ok.org.br/api/gazettes"
    params = {
        "querystring": termo,
        "territory_ids": CODIGOS_IBGE_RJ,
        "published_since": ontem_fmt_iso8601,
        "published_until": ontem_fmt_iso8601,
        "number_of_excerpts": 10,
        "excerpt_size": 1000,
        "size": 200,
        "pre_tags": "<span class=\"highlight\" style=\"background:#FFA;\">",
        "post_tags": "</span>", 
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"❌ Erro ao buscar '{termo}': {e}")
        return {"total_gazettes": 0, "gazettes": []}

def gerar_html_resultado(termo, resp_querido_diario):
    html = ""
    for diario in resp_querido_diario["gazettes"]:
        trechos = diario["excerpts"]
        if not trechos:
            continue
        trechos = "<br><br>".join(trechos)
        html += f'''
        <p><strong>📍 Município:</strong> {diario['territory_name']}<br>
        <strong>📄 Edição:</strong> <a href="{diario['url']}">{diario['url']}</a><br>
        <strong>📝 Trechos:</strong><br>{trechos}</p><hr>
        '''
    titulo = f"<h2>🔍 Termo: <em>{termo}</em> (total: {resp_querido_diario['total_gazettes']})</h2>"
    return titulo + html if html else ""

def gerar_corpo_email(titulo, termos):
    link_qd = "<a href=\"https://queridodiario.ok.org.br/cidades-disponiveis\">Querido Diário</a>"
    html = f"<html><body><h1>📬 {titulo}</h1><p>Consulta realizada nos municípios jurisdicionados disponíveis no {link_qd} </p><hr>"
    possui_resultado = False
    for termo in termos:
        resultado = buscar_termo_no_querido_diario(termo)
        if resultado["gazettes"]:
            html_termo = gerar_html_resultado(termo, resultado)
            if html_termo:
                html += html_termo
                possui_resultado = True
    html += "</body></html>"
    
    return html if possui_resultado else ""

def enviar_email(destinatarios, assunto, corpo_html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_REMETENTE, EMAIL_SENHA)
            server.sendmail(EMAIL_REMETENTE, destinatarios, msg.as_string())
            logger.info(f"✅ E-mail enviado com sucesso para os destinatarios cadastrados")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar e-mail: {e}")

def carregar_destinatarios(yaml_config):
    destinatarios = yaml_config.get("destinatarios", [])
    if isinstance(destinatarios, list):
        return destinatarios
    else:
        destinatarios_env = os.environ.get(destinatarios, "")
        return [email.strip() for email in destinatarios_env.splitlines() if email.strip()]

if __name__ == "__main__":
    for consulta in glob.glob("consultas/*.yaml"):
        logger.info(f"📁 Processando arquivo: {consulta}")
        with open(consulta, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        titulo = config.get("titulo", "") 
        termos = config.get("termos_pesquisa", [])
        destinatarios = carregar_destinatarios(config)

        if not titulo or not termos or not destinatarios:
            logger.warning(f"⚠️ Ignorado: arquivo {consulta} sem campos obrigatórios (titulo, destinatarios ou termos_pesquisa).")
            continue

        titulo += f" - DOs de {ontem_fmt_br}"
        corpo_html = gerar_corpo_email(titulo, termos)
        if not corpo_html:
            logger.warning(f"⚠️ Nenhum resultado encontrado para a consulta {consulta}.")
            continue

        enviar_email(
            destinatarios=destinatarios,
            assunto=titulo,
            corpo_html=corpo_html,
        )
