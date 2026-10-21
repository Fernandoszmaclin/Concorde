
from client.tcp_client import TCPClient


def main():
    client = TCPClient()

    username = input("Digite seu nome: ")

    try:
        client.connect()
        response = client.login(username)

        if response.get("type") != "LOGIN_OK":
            print("Erro:", response.get("message"))
            return

        print(f"\nBem-vindo, {username}!")
        print("Comandos disponíveis:")
        print("/criar NOME")
        print("/entrar NOME")
        print("/sairgrupo NOME")
        print("/grupos")
        print("/membros NOME")
        print("/grupo NOME MENSAGEM")
        print("/privado USUARIO MENSAGEM")
        print("/sair")

        while client.running:
            command = input("\n> ").strip()

            if not command:
                continue

            parts = command.split(maxsplit=2)
            action = parts[0]

            if action == "/sair":
                break

            elif action == "/criar" and len(parts) >= 2:
                client.create_group(parts[1])

            elif action == "/entrar" and len(parts) >= 2:
                client.join_group(parts[1])

            elif action == "/sairgrupo" and len(parts) >= 2:
                client.leave_group(parts[1])

            elif action == "/grupos":
                client.list_groups()

            elif action == "/membros" and len(parts) >= 2:
                client.list_members(parts[1])

            elif action == "/grupo" and len(parts) == 3:
                client.send_group_message(parts[1], parts[2])

            elif action == "/privado" and len(parts) == 3:
                client.send_private_message(parts[1], parts[2])

            else:
                print("Comando inválido.")

    except (OSError, ConnectionError, ValueError) as error:
        print("Erro:", error)

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
