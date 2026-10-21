
import socket
import threading

from shared.protocol import send_message, receive_message


class TCPClient:
    def __init__(self, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False

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
        send_message(self.socket, {
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
        send_message(self.socket, {
            "type": "PRIVATE_MESSAGE",
            "to": destination,
            "message": message
        })

    def receive_loop(self):
        while self.running:
            try:
                data = receive_message(self.socket)

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
                break

    def disconnect(self):
        self.running = False

        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            self.socket.close()
            self.socket = None

    def create_group(self, group):
        send_message(self.socket, {
            "type": "GROUP_CREATE",
            "group": group
        })

    def join_group(self, group):
        send_message(self.socket, {
            "type": "GROUP_JOIN",
            "group": group
        })

    def leave_group(self, group):
        send_message(self.socket, {
            "type": "GROUP_LEAVE",
            "group": group
        })

    def list_groups(self):
        send_message(self.socket, {
            "type": "GROUP_LIST"
        })

    def list_members(self, group):
        send_message(self.socket, {
            "type": "GROUP_MEMBERS",
            "group": group
        })

    def send_group_message(self, group, message):
        send_message(self.socket, {
            "type": "GROUP_MESSAGE",
            "group": group,
            "message": message
        })

