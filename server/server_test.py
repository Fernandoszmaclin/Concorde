## arquivo temporario so pra teste, 
## enquanto os guris estao preparando o resto



import socket
import threading

from shared.protocol import send_message, receive_message

HOST = "127.0.0.1"
PORT = 5000

clients = {}
clients_lock = threading.Lock()

groups = {}
groups_lock = threading.Lock()


def send_to_user(username, data):
    with clients_lock:
        client = clients.get(username)

    if client is None:
        return False

    try:
        with client["lock"]:
            send_message(client["conn"], data)
        return True

    except (OSError, ConnectionError):
        return False


def broadcast(data, exclude=None):
    with clients_lock:
        usernames = list(clients.keys())

    for username in usernames:
        if username != exclude:
            send_to_user(username, data)


def update_user_list():
    with clients_lock:
        usernames = list(clients.keys())

    broadcast({
        "type": "USER_LIST",
        "users": usernames
    })


def create_group(username, group_name):
    with groups_lock:
        if group_name in groups:
            return False

        groups[group_name] = {username}

    return True


def join_group(username, group_name):
    with groups_lock:
        if group_name not in groups:
            return False

        groups[group_name].add(username)

    return True


def leave_group(username, group_name):
    with groups_lock:
        if group_name not in groups:
            return False

        if username not in groups[group_name]:
            return False

        groups[group_name].remove(username)

        if not groups[group_name]:
            del groups[group_name]

    return True

def list_groups():
    with groups_lock:
        return list(groups.keys())


def list_members(group_name):
    with groups_lock:
        if group_name not in groups:
            return None

        return sorted(groups[group_name])


def send_group_message(username, group_name, message):
    with groups_lock:
        if group_name not in groups:
            return False, "Grupo não encontrado"

        if username not in groups[group_name]:
            return False, "Você não participa desse grupo"

        members = list(groups[group_name])

    for member in members:
        send_to_user(member, {
            "type": "GROUP_MESSAGE_RECEIVED",
            "group": group_name,
            "from": username,
            "message": message
        })

    return True, None

def handle_client(conn, address):
    username = None

    try:
        data = receive_message(conn)

        if not isinstance(data, dict) or data.get("type") != "LOGIN":
            send_message(conn, {
                "type": "ERROR",
                "message": "Login inválido"
            })
            return

        username = data.get("username")

        if not isinstance(username, str) or not username.strip():
            send_message(conn, {
                "type": "ERROR",
                "message": "Nome inválido"
            })
            return

        username = username.strip()

        with clients_lock:
            if username in clients:
                send_message(conn, {
                    "type": "ERROR",
                    "message": "Usuário já conectado"
                })
                return

        clients[username] = {
                "conn": conn,
                "lock": threading.Lock()
        }

        send_message(conn, {
            "type": "LOGIN_OK",
            "username": username
        })

        print(f"{username} conectado: {address}")

        update_user_list()

        broadcast({
            "type": "USER_STATUS",
            "username": username,
            "status": "online"
            }, exclude=username)

        while True:
            data = receive_message(conn)

            if not isinstance(data, dict):
                continue

            if data.get("type") == "PRIVATE_MESSAGE":
                destination = data.get("to")
                message = data.get("message")

                if not isinstance(destination, str) or not isinstance(message, str):
                    send_message(conn, {
                        "type": "ERROR",
                        "message": "Mensagem inválida"
                    })
                    continue

                with clients_lock:
                    target = clients.get(destination)

                if target:
                    try:
                        with target["lock"]:
                            send_message(target["conn"], {
                                "type": "MESSAGE_RECEIVED",
                                "from": username,
                                "message": message
                            })
                    except OSError:
                        send_message(conn, {
                            "type": "ERROR",
                            "message": "Falha ao entregar mensagem"
                        })
                else:
                    send_message(conn, {
                        "type": "ERROR",
                        "message": "Usuário não encontrado"
                    })
            
            elif data.get("type") == "GROUP_CREATE":
                group = data.get("group")

                if not isinstance(group, str) or not group.strip():
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Nome de grupo inválido"
                    })
                    continue

                if create_group(username, group):
                    send_to_user(username, {
                        "type": "GROUP_EVENT",
                        "message": f"Grupo {group} criado!"
                    })
                else:
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Esse grupo já existe"
                    })

            elif data.get("type") == "GROUP_JOIN":
                group = data.get("group")

                if not isinstance(group, str) or not group.strip():
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Nome de grupo inválido"
                    })
                    continue

                if join_group(username, group):
                    send_to_user(username, {
                        "type": "GROUP_EVENT",
                        "message": f"Você entrou em {group}"
                    })
                else:
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Grupo não encontrado"
                    })

            elif data.get("type") == "GROUP_LEAVE":
                group = data.get("group")

                if not isinstance(group, str) or not group.strip():
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Nome de grupo inválido"
                    })
                    continue

                if leave_group(username, group):
                    send_to_user(username, {
                        "type": "GROUP_EVENT",
                        "message": f"Você saiu de {group}"
                    })
                else:
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Não foi possível sair do grupo"
                    })

            elif data.get("type") == "GROUP_LIST":
                send_to_user(username, {
                    "type": "GROUP_LIST_RESULT",
                    "groups": list_groups()
                })

            elif data.get("type") == "GROUP_MEMBERS":
                group = data.get("group")

                if not isinstance(group, str):
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Nome de grupo inválido"
                    })
                    continue

                members = list_members(group)

                if members is None:
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Grupo não encontrado"
                    })
                else:
                    send_to_user(username, {
                        "type": "GROUP_MEMBERS_RESULT",
                        "group": group,
                        "members": members
                    })

            elif data.get("type") == "GROUP_MESSAGE":
                group = data.get("group")
                message = data.get("message")

                if (
                    not isinstance(group, str)
                    or not isinstance(message, str)
                    or not message.strip()
                ):
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": "Mensagem de grupo inválida"
                    })
                    continue

                success, error = send_group_message(
                    username, group, message
                )

                if not success:
                    send_to_user(username, {
                        "type": "ERROR",
                        "message": error
                    })

    except (ConnectionError, OSError, ValueError) as error:
        print("Conexão encerrada:", error)

    
    finally:
        removed = False

        if username:
            with clients_lock:
                if clients.get(username, {}).get("conn") is conn:
                    del clients[username]
                    removed = True

        conn.close()

        if removed:
            print(f"{username} desconectado.")

            with groups_lock:
                for group in list(groups.keys()):
                    groups[group].discard(username)

                    if not groups[group]:
                        del groups[group]

            update_user_list()

            broadcast({
                "type": "USER_STATUS",
                "username": username,
                "status": "offline"
            })

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind((HOST, PORT))
    server.listen()

    print("Servidor aguardando conexões...")

    while True:
        conn, address = server.accept()

        thread = threading.Thread(
            target=handle_client,
            args=(conn, address),
            daemon=True
        )

        thread.start()
