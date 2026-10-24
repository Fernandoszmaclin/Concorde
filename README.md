# Concorde

Chat em grupo por TCP e chamadas de voz por UDP, feito em Python. Requer Python 3.11 ou superior.

## Instalação

Na pasta do projeto, crie o ambiente virtual e instale a dependência de áudio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Iniciar

Abra um terminal para o servidor:

```powershell
.\.venv\Scripts\python.exe -m server.server_test
```

Abra outro terminal para cada cliente:

```powershell
.\.venv\Scripts\python.exe -m client.main
```

Escolha nomes diferentes. No primeiro cliente, crie um grupo e entre na chamada:

```text
/criar redes
/voz redes
```

Nos outros clientes, entre no grupo e na chamada:

```text
/entrar redes
/voz redes
```

Use fones para evitar retorno de áudio. Para uma conversa entre pessoas, prefira executar cada cliente em um computador diferente.

## Comandos de voz

- `/voz NOME`: entra na chamada do grupo.
- `/mute`: silencia ou ativa o microfone.
- `/sairvoz`: sai da chamada e mantém o chat conectado.
- `/dispositivos`: lista microfones e saídas disponíveis.
- `/sair`: encerra o cliente.

Os comandos de texto do chat também continuam disponíveis.

## Rede local

No computador servidor, aceite conexões da rede:

```powershell
.\.venv\Scripts\python.exe -m server.server_test --host 0.0.0.0
```

Nos clientes, informe o IPv4 do servidor, que pode ser encontrado com `ipconfig`:

```powershell
.\.venv\Scripts\python.exe -m client.main --host 192.168.1.10
```

O firewall do servidor precisa permitir TCP na porta 5000 e UDP na porta 5001. Para um cliente no próprio servidor, use `127.0.0.1`.

## Áudio

Liste os dispositivos e, se necessário, escolha os IDs do microfone e da saída:

```powershell
.\.venv\Scripts\python.exe -m client.main --list-devices
.\.venv\Scripts\python.exe -m client.main --input-device 1 --output-device 4
```

Para diagnosticar falhas de abertura, execute:

```powershell
.\.venv\Scripts\python.exe -m client.main --check-audio
```

No Windows, o cliente prioriza dispositivos WASAPI. Se o áudio falhar, confira as permissões de microfone e tente selecionar os IDs exibidos por `--list-devices`. O chat continua disponível mesmo sem áudio.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
