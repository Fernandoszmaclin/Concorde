
import argparse

from client.tcp_client import TCPClient
from client.voice_client import list_audio_devices


def main():
    parser = argparse.ArgumentParser(description="Cliente de chat e voz em grupo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--input-device", type=int, help="ID do microfone em /dispositivos")
    parser.add_argument("--output-device", type=int, help="ID da saída em /dispositivos")
    diagnostics = parser.add_mutually_exclusive_group()
    diagnostics.add_argument("--list-devices", action="store_true")
    diagnostics.add_argument("--check-audio", action="store_true",
                             help="Testa abertura no terminal atual, sem gravar áudio")
    args = parser.parse_args()
    if args.check_audio:
        from client.audio_diagnostics import check_audio
        report, success = check_audio(args.input_device, args.output_device)
        print(report)
        if not success:
            parser.exit(1)
        return
    if args.list_devices:
        try:
            print(list_audio_devices())
        except RuntimeError as error:
            parser.exit(1, f"{error}\n")
        return

    client = TCPClient(args.host, args.port, args.input_device, args.output_device)

    username = input("Digite seu nome: ")

    try:
        client.connect()
        response = client.login(username)

        if response.get("type") != "LOGIN_OK":
            print("Erro:", response.get("message"))
            return

        print(f"\nBem-vindo, {username}!")
        print("Comandos disponíveis:")
        print("/criar NOMEGRUPO")
        print("/entrar NOME")
        print("/sairgrupo NOME")
        print("/grupos")
        print("/membros NOME")
        print("/grupo NOME MENSAGEM")
        print("/privado USUARIO MENSAGEM")
        print("/voz NOME         (entre antes no grupo com /entrar ou /criar)")
        print("/sairvoz")
        print("/mute             (alterna o mute)")
        print("/dispositivos     (lista microfones e saídas)")
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

            elif action == "/voz" and len(parts) == 2:
                client.join_voice(parts[1])

            elif action == "/sairvoz":
                client.leave_voice()

            elif action == "/mute":
                client.toggle_mute()

            elif action == "/dispositivos":
                client.show_audio_devices()

            else:
                print("Comando inválido.")

    except (KeyboardInterrupt, EOFError):
        print("\nEncerrando cliente.")
    except (OSError, ConnectionError, ValueError) as error:
        print("Erro:", error)

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
