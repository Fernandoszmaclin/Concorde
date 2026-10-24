# Discord2 — chat e voz em grupo

Protótipo acadêmico em Python com mensagens TCP e voz UDP via sockets.
Requer Python 3.11 ou superior. Servidor e testes de rede usam a biblioteca
padrão. O cliente de voz usa `sounddevice` apenas para microfone e saída de áudio.

## Instalar e executar no Windows

Execute na pasta principal `Discord2`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Não é necessário ativar o ambiente virtual. Nesta máquina, ele já foi criado
e as dependências já foram instaladas.

Terminal do servidor:

```powershell
.\.venv\Scripts\python.exe -m server.server_test
```

Abra um terminal por cliente:

```powershell
.\.venv\Scripts\python.exe -m client.main
```

Use nomes diferentes. No primeiro cliente, digite um comando por vez e espere
a confirmação antes do seguinte:

```text
/criar redes
/voz redes
```

Nos demais clientes:

```text
/entrar redes
/voz redes
```

Após aparecer `Chamada em redes`, o microfone fica ativo. Todos os participantes
da chamada ouvem os demais. Use fones; para avaliar conversa real, prefira um
cliente por computador, pois vários clientes na mesma máquina compartilham
dispositivos e podem gerar realimentação acústica.

| Comando | Efeito |
| --- | --- |
| `/voz redes` | Entra na chamada do grupo do qual você já participa |
| `/mute` | Alterna entre enviar microfone e enviar silêncio |
| `/sairvoz` | Encerra a voz e mantém o chat conectado |
| `/sairgrupo redes` | Sai do grupo e também de sua chamada, se estiver nela |
| `/dispositivos` | Lista IDs dos dispositivos de áudio |
| `/sair` | Encerra voz e conexão TCP |

Os comandos de texto anteriores continuam disponíveis.

## Usar computadores na mesma rede local

Na máquina do servidor:

```powershell
.\.venv\Scripts\python.exe -m server.server_test --host 0.0.0.0
```

Nos outros computadores, substitua o IP abaixo pelo IPv4 da máquina do servidor,
obtido com `ipconfig`:

```powershell
.\.venv\Scripts\python.exe -m client.main --host 192.168.1.10
```

O cliente executado na própria máquina do servidor pode usar `127.0.0.1`.
`0.0.0.0` é endereço de escuta, não endereço de destino. O firewall da máquina
servidora precisa permitir TCP 5000 e UDP 5001 na rede privada usada no teste.
O programa não altera o firewall automaticamente.

## Escolher microfone e saída

```powershell
.\.venv\Scripts\python.exe -m client.main --list-devices
.\.venv\Scripts\python.exe -m client.main --input-device 1 --output-device 4
```

Os números são exemplos: consulte a lista na sua máquina. Se houver falha ao abrir
o áudio, confira permissões de microfone do Windows, conexão dos dispositivos e
suporte a mono/16 kHz. No Windows, a seleção automática prefere os dispositivos
padrão da API **Windows WASAPI**, em modo compartilhado e com conversão do sistema.
Se essa abertura falhar, tenta o dispositivo padrão comum; cada dispositivo também
é tentado com latência mais alta. IDs explícitos são respeitados.

Para erros `MME error 11` / `PaErrorCode -9999`, liste os dispositivos e escolha os
IDs das linhas **Windows WASAPI** correspondentes ao seu microfone e fone. Feche
e abra novamente o cliente após atualizar o código. O chat continua funcionando
quando o áudio falha. A abertura informa na tela os dispositivos e APIs utilizados.

Se a falha continuar, execute o diagnóstico **no mesmo terminal** que apresentou
o erro:

```powershell
.\.venv\Scripts\python.exe -m client.main --check-audio
```

Esse comando não conecta ao servidor nem inicia captura/reprodução. Ele informa
o interpretador e a versão do driver e tenta abrir/fechar os dispositivos na
thread principal e em uma thread secundária. A opção `--list-devices` apenas lista
dispositivos; seu sucesso não comprova que o microfone pode ser aberto.

Se necessário, compare com o mesmo diagnóstico em PowerShell aberto separadamente
do VS Code, na pasta do projeto. Se apenas a thread secundária falhar, investigue
a inicialização do áudio entre threads. Se ambas falharem apenas num ambiente,
investigue as diferenças entre os processos. Não é necessário executar como
administrador nem modificar permissões automaticamente.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam sockets reais em loopback e áudio sintético: não gravam o microfone
nem reproduzem som. Incluem encaminhamento em grupo, isolamento entre grupos,
controle TCP, mute, limpeza, reconexão à chamada e tratamento de perdas/reordenação.

Leia [a explicação da implementação](docs/voz.md) para estudar o fluxo, os loops,
o formato dos pacotes e os motivos das decisões.
