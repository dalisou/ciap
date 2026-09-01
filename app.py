from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from email.message import EmailMessage
from datetime import datetime, timedelta
import json
import os
import secrets
import smtplib
import socket
import sys

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "db.json"
SESSION_TTL_SECONDS = 60 * 60 * 12

ADMIN_USER = os.environ.get("ADMIN_USER", "ciap")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "CIAP2026")
EMAIL_TO = os.environ.get("EMAIL_TO", "ciapcadastro@gmail.com")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465") or 465)
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

SESSIONS = {}
DEFAULT_AVAILABILITY = [
    {"dia": "2026-09-07", "horarios": ["09:00", "10:30", "14:00", "15:30"]},
    {"dia": "2026-09-08", "horarios": ["09:30", "11:00", "13:30", "16:00"]},
    {"dia": "2026-09-09", "horarios": ["08:30", "10:00", "14:30", "17:00"]},
    {"dia": "2026-09-10", "horarios": ["09:00", "12:00", "15:00"]},
    {"dia": "2026-09-11", "horarios": ["10:00", "13:00", "16:30"]},
    {"dia": "2026-09-12", "horarios": ["08:00", "09:30", "11:30", "15:30"]},
    {"dia": "2026-09-13", "horarios": ["09:00", "11:00", "14:00", "16:00"]},
]


def ensure_db():
    DATA_DIR.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.write_text(json.dumps({"disponibilidade": DEFAULT_AVAILABILITY, "agendamentos": []}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_db():
    ensure_db()
    try:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"disponibilidade": DEFAULT_AVAILABILITY, "agendamentos": []}
        save_db(data)
        return data


def save_db(data):
    ensure_db()
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a, %d/%m/%Y")
    except ValueError:
        return date_str


def create_session(username):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"username": username, "expires": (datetime.now() + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat()}
    return token


def session_is_valid(token):
    session = SESSIONS.get(token)
    if not session:
        return False
    expires = datetime.fromisoformat(session["expires"])
    if datetime.now() > expires:
        SESSIONS.pop(token, None)
        return False
    return True


def get_session_token(handler):
    cookie_header = handler.headers.get("Cookie", "")
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    morsel = cookie.get("ciap_session")
    return morsel.value if morsel else None


def is_admin_authenticated(handler):
    token = get_session_token(handler)
    return bool(token and session_is_valid(token))


def build_report_text():
    db = load_db()
    agendamentos = db.get("agendamentos", [])
    if not agendamentos:
        return "Nenhum agendamento registrado até o momento."

    lines = ["RELATÓRIO DE AGENDAMENTOS - CIAP", ""]
    for i, item in enumerate(agendamentos, start=1):
        lines.append(
            f"{i}. Nome: {item.get('nomeCompleto', '-')}; CPF: {item.get('cpf', '-')}; "
            f"Processo: {item.get('numeroProcesso', '-')}; Data: {item.get('diaAgendamento', '-')}; "
            f"Hora: {item.get('horaAgendamento', '-')}; Cadastro: {item.get('dataCadastro', '-')}"
        )
    return "\n".join(lines)


def send_report_email(report_text):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        local_path = DATA_DIR / "relatorio_email.txt"
        local_path.write_text(report_text, encoding="utf-8")
        return False, "SMTP não configurado. Arquivo de relatório salvo localmente."

    try:
        message = EmailMessage()
        message["Subject"] = "Relatório de agendamentos CIAP"
        message["From"] = SMTP_USER
        message["To"] = EMAIL_TO
        message.set_content(report_text)

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return True, "Relatório enviado com sucesso para o e-mail da CIAP."
    except Exception as exc:
        local_path = DATA_DIR / "relatorio_email.txt"
        local_path.write_text(report_text, encoding="utf-8")
        return False, f"Erro no envio automático: {exc}. Relatório salvo localmente."


class SiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        print(f"[site] {self.address_string()} - {format % args}")

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def api_disponibilidade(self):
        db = load_db()
        self.send_json({"semana": db.get("disponibilidade", DEFAULT_AVAILABILITY)})

    def api_agendamentos_list(self):
        db = load_db()
        self.send_json({"agendamentos": db.get("agendamentos", [])})

    def api_agendamentos_create(self):
        payload = self.read_json_body()
        nome = str(payload.get("nomeCompleto", "")).strip()
        cpf = str(payload.get("cpf", "")).strip()
        processo = str(payload.get("numeroProcesso", "")).strip()
        dia = str(payload.get("diaAgendamento", "")).strip()
        hora = str(payload.get("horaAgendamento", "")).strip()

        if not all([nome, cpf, processo, dia, hora]):
            self.send_json({"error": "Preencha todos os campos do agendamento."}, 400)
            return

        db = load_db()
        agendamentos = db.setdefault("agendamentos", [])
        agendamentos.append(
            {
                "nomeCompleto": nome,
                "cpf": cpf,
                "numeroProcesso": processo,
                "diaAgendamento": dia,
                "horaAgendamento": hora,
                "dataCadastro": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_db(db)
        report_text = build_report_text()
        sent, message = send_report_email(report_text)
        self.send_json({
            "ok": True,
            "message": "Agendamento salvo com sucesso.",
            "emailSent": sent,
            "reportMessage": message,
            "relatorio": report_text,
        })

    def api_relatorio(self):
        report_text = build_report_text()
        sent, message = send_report_email(report_text)
        self.send_json({"emailSent": sent, "message": message, "relatorio": report_text})

    def api_admin_login(self):
        payload = self.read_json_body()
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        if username == ADMIN_USER and password == ADMIN_PASS:
            token = create_session(username)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", f"ciap_session={token}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "message": "Login realizado."}, ensure_ascii=False).encode("utf-8"))
            return
        self.send_json({"ok": False, "message": "Credenciais inválidas."}, 401)

    def api_admin_logout(self):
        token = get_session_token(self)
        if token:
            SESSIONS.pop(token, None)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", "ciap_session=; Path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "message": "Logout realizado."}, ensure_ascii=False).encode("utf-8"))

    def api_admin_check(self):
        self.send_json({"authenticated": is_admin_authenticated(self)})

    def api_admin_disponibilidade_get(self):
        if not is_admin_authenticated(self):
            self.send_json({"error": "Não autenticado."}, 401)
            return
        db = load_db()
        self.send_json({"disponibilidade": db.get("disponibilidade", DEFAULT_AVAILABILITY)})

    def api_admin_disponibilidade_post(self):
        if not is_admin_authenticated(self):
            self.send_json({"error": "Não autenticado."}, 401)
            return
        payload = self.read_json_body()
        dia = str(payload.get("dia", "")).strip()
        horarios = payload.get("horarios", [])
        if not dia or not isinstance(horarios, list):
            self.send_json({"error": "Informe a data e os horários."}, 400)
            return
        lista = [str(h).strip() for h in horarios if str(h).strip()]
        if not lista:
            self.send_json({"error": "Informe pelo menos um horário válido."}, 400)
            return

        db = load_db()
        items = db.setdefault("disponibilidade", [])
        existing = next((item for item in items if item.get("dia") == dia), None)
        if existing:
            existing["horarios"] = lista
        else:
            items.append({"dia": dia, "horarios": lista})
        items.sort(key=lambda item: item.get("dia", ""))
        save_db(db)
        self.send_json({"ok": True, "disponibilidade": items})

    def api_admin_disponibilidade_delete(self):
        if not is_admin_authenticated(self):
            self.send_json({"error": "Não autenticado."}, 401)
            return

        query = parse_qs(urlparse(self.path).query)
        dia = str(query.get("dia", [""])[0]).strip()
        if not dia:
            self.send_json({"error": "Informe a data para remover."}, 400)
            return
        db = load_db()
        items = db.get("disponibilidade", [])
        db["disponibilidade"] = [item for item in items if item.get("dia") != dia]
        save_db(db)
        self.send_json({"ok": True, "disponibilidade": db["disponibilidade"]})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/disponibilidade":
            self.api_disponibilidade(); return
        if path == "/api/agendamentos":
            self.api_agendamentos_list(); return
        if path == "/api/relatorio":
            self.api_relatorio(); return
        if path == "/api/admin/check":
            self.api_admin_check(); return
        if path == "/api/admin/disponibilidade":
            self.api_admin_disponibilidade_get(); return
        if path == "/api/admin/logout":
            self.api_admin_logout(); return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/agendamentos":
            self.api_agendamentos_create(); return
        if path == "/api/admin/login":
            self.api_admin_login(); return
        if path == "/api/admin/disponibilidade":
            self.api_admin_disponibilidade_post(); return
        self.send_json({"error": "Rota não encontrada."}, 404)

    def do_DELETE(self):
        if urlparse(self.path).path == "/api/admin/disponibilidade":
            self.api_admin_disponibilidade_delete(); return
        self.send_json({"error": "Rota não encontrada."}, 404)


def port_is_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    ensure_db()
    port = int(os.environ.get("PORT", 8000))

    if not port_is_available(port):
        print(f"Erro: a porta {port} já está em uso.", file=sys.stderr)
        print("Feche a instância anterior do projeto ou use outra porta, por exemplo:", file=sys.stderr)
        print("PORT=8001 python app.py", file=sys.stderr)
        raise SystemExit(1)

    print(f"CIAP-PB disponível na porta {port}")
    print(f"Usuário do painel: {ADMIN_USER}")
    print(f"E-mail de destino: {EMAIL_TO}")
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), SiteHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
        raise SystemExit(0)
