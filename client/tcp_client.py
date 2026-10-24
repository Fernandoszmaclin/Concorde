
import socket
import threading

from shared.protocol import send_message, receive_message
from client.voice_client import VoiceClient, list_audio_devices


class TCPClient:
    def __init__(self, host="127.0.0.1", port=5000,
                 input_device=None, output_device=None):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        # Comandos do terminal e eventos da voz podem enviar TCP simultaneamente.
        self.send_lock = threading.Lock()
        self.voice_lock = threading.RLock()
        self.voice = None
        self.voice_pending = None
        self.voice_leaving = False
        self.input_device = input_device
        self.output_device = output_device

    def _send(self, data):
        with self.send_lock:
            if self.socket is None:
                raise ConnectionError("Cliente desconectado")
            send_message(self.socket, data)

    def connect(self):
        self.socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        try:
            self.socket.connect((self.host, self.port))
        except OSError:
            self.socket.close()
            self.socket = None
            raise

    def login(self, username):
        self._send({
            "type": "LOGIN",
            "username": username
        })

        response = receive_message(self.socket)

        if response.get("type") == "LOGIN_OK":
            self.running = True

            threading.Thread(
                target=self.receive_loop,
                daemon=True
            ).start()

        return response

    def send_private_message(self, destination, message):
        self._send({
            "type": "PRIVATE_MESSAGE",
            "to": destination,
            "message": message
        })

    def receive_loop(self):
        while self.running:
            try:
                data = receive_message(self.socket)

                if not isinstance(data, dict):
                    continue

                kind = data.get("type")
                if isinstance(kind, str) and kind.startswith("VOICE_"):
                    self._handle_voice_event(data)
                    continue

                if data.get("type") == "MESSAGE_RECEIVED":
                    print(
                        f"\n[{data['from']}]: {data['message']}"
                    )
                
                elif data.get("type") == "USER_LIST":
                    users = data.get("users", [])

                    print("\n--- Usuários conectados ---")

                    for user in users:
                        print(f"• {user}")

                    print("--------------------------")


                elif data.get("type") == "USER_STATUS":
                    username = data.get("username")
                    status = data.get("status")

                    if status == "online":
                        print(f"\n{username} entrou no sistema.")

                    elif status == "offline":
                        print(f"\n{username} saiu do sistema.")

                elif data.get("type") == "ERROR":
                    print("\nErro:", data.get("message"))

                
                elif data.get("type") == "GROUP_EVENT":
                    print("\n", data.get("message"))

                elif data.get("type") == "GROUP_LIST_RESULT":
                    print("\n--- Grupos disponíveis ---")

                    for group in data.get("groups", []):
                        print(f"• {group}")

                elif data.get("type") == "GROUP_MEMBERS_RESULT":
                    print(f"\n--- Grupo: {data.get('group')} ---")

                    for member in data.get("members", []):
                        print(f"• {member}")

                elif data.get("type") == "GROUP_MESSAGE_RECEIVED":
                    print(
                        f"\n[{data.get('group')}] "
                        f"{data.get('from')}: "
                        f"{data.get('message')}"
                    )

            except (ConnectionError, OSError, ValueError):
                if self.running:
                    print("\nConexão com servidor perdida.")
                self.running = False
                self._stop_voice()
                break

    def disconnect(self):
        self.running = False
        # Fechar a conexão TCP faz o servidor também revogar o token de voz.
        self._stop_voice()

        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            self.socket.close()
            self.socket = None

    def create_group(self, group):
        self._send({
            "type": "GROUP_CREATE",
            "group": group
        })

    def join_group(self, group):
        self._send({
            "type": "GROUP_JOIN",
            "group": group
        })

    def leave_group(self, group):
        self._send({
            "type": "GROUP_LEAVE",
            "group": group
        })

    def list_groups(self):
        self._send({
            "type": "GROUP_LIST"
        })

    def list_members(self, group):
        self._send({
            "type": "GROUP_MEMBERS",
            "group": group
        })

    def send_group_message(self, group, message):
        self._send({
            "type": "GROUP_MESSAGE",
            "group": group,
            "message": message
        })

    def join_voice(self, group):
        with self.voice_lock:
            if self.voice is not None or self.voice_pending or self.voice_leaving:
                print("\n[Voz] Já existe chamada ativa ou operação em andamento. Use /sairvoz.")
                return
            self.voice_pending = group
            try:
                self._send({"type": "VOICE_JOIN", "group": group})
            except (OSError, ConnectionError):
                self.voice_pending = None
                raise

    def leave_voice(self):
        with self.voice_lock:
            self.voice_leaving = True
            self._stop_voice()
            self._send({"type": "VOICE_LEAVE"})

    def toggle_mute(self):
        with self.voice_lock:
            if self.voice is None:
                print("\n[Voz] Entre em uma chamada com /voz NOME.")
                return
            muted = not self.voice.muted.is_set()
            self.voice.set_muted(muted)
            print("\n[Voz] Microfone " + ("silenciado." if muted else "ativado."))

    def show_audio_devices(self):
        try:
            print(list_audio_devices())
        except RuntimeError as error:
            print(f"\n[Voz] {error}")

    def _stop_voice(self):
        with self.voice_lock:
            if self.voice is not None:
                self.voice.stop()
                self.voice = None
            self.voice_pending = None

    def _handle_voice_event(self, data):
        with self.voice_lock:
            kind = data.get("type")
            if kind == "VOICE_JOINED":
                if self.voice_leaving or self.voice_pending != data["group"]:
                    return
                try:
                    # Usamos o IP efetivo do servidor TCP, inclusive na rede local.
                    voice = VoiceClient(
                        self.socket.getpeername()[0], data["port"], data["token"],
                        data["group"], self.input_device, self.output_device,
                    )
                    voice.start()
                    self.voice = voice
                    self.voice_pending = None
                    print(f"\n[Voz] Chamada em {data['group']}. Use fones; /mute ou /sairvoz.")
                except Exception as error:
                    self.voice_pending = None
                    self.voice_leaving = True
                    self._send({"type": "VOICE_LEAVE"})
                    print(f"\n[Voz] Não foi possível iniciar: {error}")
            elif kind == "VOICE_PARTICIPANTS":
                if self.voice is not None and self.voice.group == data["group"]:
                    participants = data["participants"]
                    if not self.voice.set_participants(participants, data["revision"]):
                        return
                    names = ", ".join(p["username"] for p in participants)
                    print(f"\n[Voz] Participantes de {data['group']}: {names}")
            elif kind == "VOICE_LEFT":
                self._stop_voice()
                self.voice_leaving = False
                print("\n[Voz] Você saiu da chamada.")
            elif kind == "VOICE_ERROR":
                self.voice_pending = None
                print("\n[Voz] Erro:", data.get("message"))

