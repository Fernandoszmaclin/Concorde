
"use strict";

/*
 * Concorde — controle da interface.
 */

const $ = (seletor, elemento = document) => elemento.querySelector(seletor);
const CHAVE_LOCAL = "concorde-demo-v1";
const HORARIO = () => new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit", minute: "2-digit"
});

const estado = {
    modo: "demo",          // demo | online | offline
    servidorDisponivel: false,
    nome: "Você",
    token: null,
    eventos: null,
    atual: { tipo: "grupo", nome: "geral" },
    usuarios: new Set(),
    contatos: new Set(),
    grupos: new Set(),
    participantes: {},
    inscritos: new Set(),
    conversas: {},
    pendencia: null
};

const secoes = {
    grupos: $("#grupos"),
    contatos: $("#contatos"),
    busca: $('.area-busca input'),
    mensagens: $(".mensagens"),
    entrada: $(".campo-mensagem input"),
    enviar: $(".botao-enviar"),
    membros: $(".painel-membros"),
    perfil: $(".perfil"),
    aviso: $(".rodape-chat > p"),
    etiqueta: $(".etiqueta")
};

function chaveConversa(tipo, nome) {
    return `${tipo}:${nome}`;
}

function lerLocal() {
    try {
        return JSON.parse(localStorage.getItem(CHAVE_LOCAL) || "null");
    } catch (_) {
        return null;
    }
}

function salvarLocal() {
    if (estado.modo !== "demo") return;
    const dados = {
        nome: estado.nome,
        atual: estado.atual,
        contatos: [...estado.contatos],
        grupos: [...estado.grupos],
        inscritos: [...estado.inscritos],
        participantes: estado.participantes,
        conversas: estado.conversas
    };
    try { localStorage.setItem(CHAVE_LOCAL, JSON.stringify(dados)); }
    catch (_) { avisar("Não foi possível salvar os dados no navegador.", true); }
}

function iniciarDemonstracao() {
    const dados = lerLocal();
    estado.modo = "demo";
    estado.token = null;
    estado.nome = typeof dados?.nome === "string" ? dados.nome : "Você";
    estado.atual = dados?.atual || { tipo: "grupo", nome: "geral" };
    estado.usuarios = new Set([estado.nome, "Ana", "Bruno"]);
    estado.contatos = new Set(dados?.contatos || ["Ana", "Bruno", "Carla"]);
    estado.grupos = new Set(dados?.grupos || ["geral", "projeto-redes", "avisos"]);
    estado.inscritos = new Set(dados?.inscritos || ["geral", "projeto-redes", "avisos"]);
    estado.participantes = dados?.participantes || {
        geral: [estado.nome, "Ana", "Bruno", "Carla"],
        "projeto-redes": [estado.nome, "Ana", "Bruno"],
        avisos: [estado.nome, "Carla"]
    };
    estado.conversas = dados?.conversas || {
        "grupo:geral": [
            { de: "Ana", texto: "Boa noite, pessoal! Como está o trabalho de Redes?", hora: "18:42" },
            { de: "Bruno", texto: "O servidor TCP já recebe as mensagens. Falta a interface.", hora: "18:44" },
            { de: estado.nome, texto: "Estou preparando o Concorde!", hora: "18:46" }
        ],
        "privado:Ana": [{ de: "Ana", texto: "Você viu o código?", hora: "18:40" }],
        "privado:Bruno": [{ de: "Bruno", texto: "Reunião às 19h", hora: "18:41" }],
        "privado:Carla": [{ de: "Carla", texto: "Até amanhã!", hora: "18:43" }]
    };
    desenharTudo();
}

function criarElemento(tag, classe, texto) {
    const elemento = document.createElement(tag);
    if (classe) elemento.className = classe;
    if (texto !== undefined) elemento.textContent = texto;
    return elemento;
}

function avatar(nome, online = false) {
    const cores = ["avatar-roxo", "avatar-azul", "avatar-laranja", "avatar-usuario"];
    const cor = nome === estado.nome ? "avatar-usuario" :
        cores[[...nome].reduce((n, c) => n + c.charCodeAt(0), 0) % 3];
    const figura = criarElemento("span", `avatar ${cor}`, nome.charAt(0).toUpperCase());
    if (online) figura.append(criarElemento("span", "status"));
    return figura;
}

function botaoSecao(rotulo, titulo, acao) {
    const botao = criarElemento("button", "botao-pequeno", rotulo);
    botao.type = "button";
    botao.title = titulo;
    botao.setAttribute("aria-label", titulo);
    botao.addEventListener("click", acao);
    return botao;
}

function itemConversa(tipo, nome) {
    const selecionado = estado.atual?.tipo === tipo && estado.atual?.nome === nome;
    const item = criarElemento("button", `item-conversa${selecionado ? " selecionado" : ""}`);
    item.type = "button";
    item.dataset.nome = nome;
    item.dataset.tipo = tipo;
    item.append(tipo === "grupo" ? criarElemento("span", "icone-canal", "#") :
        avatar(nome, estado.usuarios.has(nome)));
    const dados = criarElemento("span", "dados-conversa");
    dados.append(criarElemento("strong", "", nome));
    const historico = estado.conversas[chaveConversa(tipo, nome)] || [];
    const ultima = historico[historico.length - 1];
    dados.append(criarElemento("small", "", tipo === "grupo" ?
        (estado.inscritos.has(nome) ? "Participando" : "Entrar no grupo") :
        (ultima ? ultima.texto : estado.usuarios.has(nome) ? "Online" : "Offline")));
    item.append(dados);
    item.addEventListener("click", () => selecionar(tipo, nome));
    return item;
}

function desenharLateral() {
    const filtro = secoes.busca.value.trim().toLocaleLowerCase("pt-BR");
    const criarLista = (secao, titulo, tipo, nomes, botoes) => {
        secao.replaceChildren();
        const barra = criarElemento("div", "titulo-secao");
        barra.append(criarElemento("h2", "", titulo));
        const acoes = criarElemento("div", "acoes-secao");
        botoes.forEach(b => acoes.append(b));
        barra.append(acoes);
        secao.append(barra);
        const filtrados = nomes.filter(nome => nome.toLocaleLowerCase("pt-BR").includes(filtro));
        filtrados.forEach(nome => secao.append(itemConversa(tipo, nome)));
        if (!filtrados.length) secao.append(criarElemento("p", "lista-vazia", "Nenhum resultado"));
    };
    criarLista(secoes.grupos, "Grupos", "grupo", [...estado.grupos].sort(), [
        botaoSecao("+", "Criar grupo", criarGrupo),
        botaoSecao("↳", "Entrar em grupo", entrarGrupoPorNome)
    ]);
    criarLista(secoes.contatos, "Mensagens privadas", "privado", [...estado.contatos].sort(), [
        botaoSecao("+", "Nova conversa privada", iniciarPrivado)
    ]);
    secoes.perfil.replaceChildren();
    secoes.perfil.append(avatar(estado.nome, estado.modo === "online" || estado.modo === "demo"));
    const nome = criarElemento("div", "dados-conversa");
    nome.append(criarElemento("strong", "", estado.nome));
    nome.append(criarElemento("small", "", estado.modo === "online" ? "Conectado" :
        estado.modo === "demo" ? "Demonstração local" : "Desconectado"));
    secoes.perfil.append(nome);
    const botao = criarElemento("button", "botao-perfil", estado.modo === "online" ? "Sair" :
        estado.servidorDisponivel ? "Conectar" : "Conta");
    botao.type = "button";
    botao.addEventListener("click", configurarConta);
    secoes.perfil.append(botao);
}

function desenharCabecalho() {
    const nome = estado.atual?.nome;
    const tipo = estado.atual?.tipo;
    $(".simbolo-canal").textContent = tipo === "grupo" ? "#" : "@";
    $(".identificacao-canal h2").textContent = nome || "Concorde";
    $(".identificacao-canal p").textContent = !nome ? "Selecione uma conversa" :
        tipo === "grupo" ? "Conversa em grupo" : `Conversa privada com ${nome}`;
    secoes.etiqueta.textContent = estado.modo === "online" ? "● Conectado ao TCP" :
        estado.modo === "demo" ? "● Demonstração local" : "● Desconectado";
    secoes.aviso.textContent = estado.modo === "online" ?
        "Mensagens enviadas pela ponte HTTP/SSE para o servidor TCP. Não há histórico permanente." :
        "Demonstração: as mensagens ficam neste navegador; não são enviadas para outros usuários.";
    const podeEnviar = !!nome && estado.modo !== "offline" &&
        (tipo !== "grupo" || estado.inscritos.has(nome));
    secoes.entrada.disabled = !podeEnviar;
    secoes.enviar.disabled = !podeEnviar;
    secoes.entrada.placeholder = !nome ? "Selecione uma conversa" :
        !podeEnviar ? "Entre neste grupo para enviar mensagens" :
        `Mensagem para ${tipo === "grupo" ? "#" : "@"}${nome}`;
}

function desenharMensagens() {
    secoes.mensagens.replaceChildren();
    const { tipo, nome } = estado.atual || {};
    if (!nome) {
        secoes.mensagens.append(criarElemento("div", "apresentacao-grupo", "Selecione uma conversa para começar."));
        return;
    }
    const abertura = criarElemento("div", "apresentacao-grupo");
    abertura.append(criarElemento("div", "icone-grupo", tipo === "grupo" ? "#" : "@"));
    abertura.append(criarElemento("h2", "", tipo === "grupo" ? `Bem-vindo ao #${nome}` : `Conversa com ${nome}`));
    abertura.append(criarElemento("p", "", estado.modo === "demo" ?
        "Esta é uma demonstração local, sem conexão com outras pessoas." :
        "As mensagens desta sessão aparecerão aqui."));
    secoes.mensagens.append(abertura);
    const historico = estado.conversas[chaveConversa(tipo, nome)] || [];
    if (historico.length) {
        const divisor = criarElemento("div", "divisor-data");
        divisor.append(criarElemento("span", "", "Mensagens desta sessão"));
        secoes.mensagens.append(divisor);
    }
    historico.forEach(mensagem => {
        const artigo = criarElemento("article", "mensagem");
        artigo.append(avatar(mensagem.de));
        const corpo = criarElemento("div", "corpo-mensagem");
        const meta = criarElemento("div", "meta-mensagem");
        meta.append(criarElemento("strong", "", mensagem.de));
        meta.append(criarElemento("time", "", mensagem.hora));
        corpo.append(meta, criarElemento("p", "", mensagem.texto));
        artigo.append(corpo);
        secoes.mensagens.append(artigo);
    });
    secoes.mensagens.scrollTop = secoes.mensagens.scrollHeight;
}

function desenharMembros() {
    secoes.membros.replaceChildren();
    const { tipo, nome } = estado.atual || {};
    if (tipo !== "grupo" || !nome) {
        secoes.membros.append(criarElemento("h2", "", "Conversa privada"));
        secoes.membros.append(criarElemento("p", "subtitulo-membros", "Selecione um grupo para ver membros."));
        return;
    }
    const membros = estado.participantes[nome] || [];
    secoes.membros.append(criarElemento("h2", "", `Membros — ${membros.length}`));
    const acao = criarElemento("button", "botao-grupo",
        estado.inscritos.has(nome) ? "Sair do grupo" : "Entrar no grupo");
    acao.type = "button";
    acao.addEventListener("click", () => estado.inscritos.has(nome) ? sairGrupo(nome) : entrarGrupo(nome));
    secoes.membros.append(acao);
    if (!membros.length) secoes.membros.append(criarElemento("p", "subtitulo-membros", "Nenhum membro listado"));
    const online = membros.filter(m => estado.usuarios.has(m));
    const offline = membros.filter(m => !estado.usuarios.has(m));
    for (const [titulo, lista, estaOnline] of [
        ["ONLINE", online, true], ["OFFLINE", offline, false]
    ]) {
        if (!lista.length) continue;
        secoes.membros.append(criarElemento("p", "subtitulo-membros", `${titulo} — ${lista.length}`));
        lista.forEach(membro => {
            const linha = criarElemento("div", `membro${estaOnline ? "" : " offline"}`);
            linha.append(avatar(membro, estaOnline), criarElemento("span", "", membro));
            secoes.membros.append(linha);
        });
    }
}

function desenharTudo() {
    if (!estado.atual || (estado.atual.tipo === "grupo" && !estado.grupos.has(estado.atual.nome))) {
        const primeiroGrupo = [...estado.grupos][0];
        const primeiroContato = [...estado.contatos][0];
        estado.atual = primeiroGrupo ? { tipo: "grupo", nome: primeiroGrupo } :
            primeiroContato ? { tipo: "privado", nome: primeiroContato } : null;
    }
    desenharLateral();
    desenharCabecalho();
    desenharMensagens();
    desenharMembros();
}

function selecionar(tipo, nome) {
    estado.atual = { tipo, nome };
    desenharTudo();
    salvarLocal();
    if (estado.modo === "online" && tipo === "grupo") {
        enviarComando({ type: "GROUP_MEMBERS", group: nome }).catch(erro => avisar(erro.message, true));
    }
}

function registrarMensagem(tipo, nome, de, texto, hora = HORARIO()) {
    const chave = chaveConversa(tipo, nome);
    if (!estado.conversas[chave]) estado.conversas[chave] = [];
    estado.conversas[chave].push({ de, texto, hora });
    desenharTudo();
    salvarLocal();
}

function avisar(texto, erro = false) {
    let elemento = $(".concorde-aviso");
    if (!elemento) {
        elemento = criarElemento("div", "concorde-aviso");
        elemento.setAttribute("role", "status");
        elemento.setAttribute("aria-live", "polite");
        document.body.append(elemento);
    }
    elemento.textContent = texto;
    elemento.classList.toggle("erro", erro);
    clearTimeout(avisar.temporizador);
    avisar.temporizador = setTimeout(() => elemento.remove(), 4500);
}

async function enviarComando(comando) {
    if (estado.modo !== "online") throw new Error("Sem conexão com o servidor TCP.");
    const resposta = await fetch("/api/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: estado.token, ...comando })
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.error || "Não foi possível enviar o comando.");
}

async function enviarMensagem() {
    const texto = secoes.entrada.value.trim();
    const atual = estado.atual;
    if (!texto || !atual) return;
    if (texto.length > 4000) return avisar("A mensagem deve ter no máximo 4000 caracteres.", true);
    if (atual.tipo === "grupo" && !estado.inscritos.has(atual.nome)) {
        return avisar("Você precisa participar do grupo.", true);
    }
    secoes.enviar.disabled = true;
    try {
        if (estado.modo === "online") {
            await enviarComando(atual.tipo === "grupo" ?
                { type: "GROUP_MESSAGE", group: atual.nome, message: texto } :
                { type: "PRIVATE_MESSAGE", to: atual.nome, message: texto });
            // O servidor devolve mensagens de grupo, mas não ecoa as privadas ao remetente.
            if (atual.tipo === "privado") registrarMensagem("privado", atual.nome, estado.nome, texto);
        } else if (estado.modo === "demo") {
            registrarMensagem(atual.tipo, atual.nome, estado.nome, texto);
        } else {
            throw new Error("Conexão encerrada. Entre novamente.");
        }
        secoes.entrada.value = "";
        secoes.entrada.focus();
    } catch (erro) {
        avisar(erro.message, true);
    } finally {
        desenharCabecalho();
    }
}

function nomeValido(texto) {
    return typeof texto === "string" && texto.trim().length > 0 && texto.trim().length <= 100;
}

async function criarGrupo() {
    const nome = prompt("Nome do novo grupo (até 100 caracteres):");
    if (nome === null) return;
    if (!nomeValido(nome)) return avisar("Informe um nome de grupo válido.", true);
    const grupo = nome.trim();
    if (estado.grupos.has(grupo)) return avisar("Esse grupo já existe na lista.", true);
    if (estado.modo === "online") {
        estado.pendencia = { acao: "criar", grupo };
        try { await enviarComando({ type: "GROUP_CREATE", group: grupo }); }
        catch (erro) { estado.pendencia = null; avisar(erro.message, true); }
    } else if (estado.modo === "demo") {
        estado.grupos.add(grupo);
        estado.inscritos.add(grupo);
        estado.participantes[grupo] = [estado.nome];
        selecionar("grupo", grupo);
        salvarLocal();
        avisar(`Grupo #${grupo} criado localmente.`);
    }
}

async function entrarGrupoPorNome() {
    const nome = prompt("Digite o nome do grupo em que deseja entrar:");
    if (nome === null) return;
    if (!nomeValido(nome)) return avisar("Nome de grupo inválido.", true);
    await entrarGrupo(nome.trim());
}

async function entrarGrupo(grupo) {
    if (estado.inscritos.has(grupo)) return avisar("Você já participa desse grupo.");
    if (estado.modo === "online") {
        estado.pendencia = { acao: "entrar", grupo };
        try { await enviarComando({ type: "GROUP_JOIN", group: grupo }); }
        catch (erro) { estado.pendencia = null; avisar(erro.message, true); }
    } else if (estado.modo === "demo") {
        if (!estado.grupos.has(grupo)) return avisar("Grupo não encontrado na demonstração.", true);
        estado.inscritos.add(grupo);
        const membros = estado.participantes[grupo] || [];
        if (!membros.includes(estado.nome)) membros.push(estado.nome);
        estado.participantes[grupo] = membros;
        selecionar("grupo", grupo);
        avisar(`Você entrou em #${grupo} (localmente).`);
    }
}

async function sairGrupo(grupo) {
    if (!estado.inscritos.has(grupo)) return;
    if (!confirm(`Sair do grupo #${grupo}?`)) return;
    if (estado.modo === "online") {
        estado.pendencia = { acao: "sair", grupo };
        try { await enviarComando({ type: "GROUP_LEAVE", group: grupo }); }
        catch (erro) { estado.pendencia = null; avisar(erro.message, true); }
    } else if (estado.modo === "demo") {
        estado.inscritos.delete(grupo);
        estado.participantes[grupo] = (estado.participantes[grupo] || []).filter(n => n !== estado.nome);
        desenharTudo();
        salvarLocal();
        avisar(`Você saiu de #${grupo} (localmente).`);
    }
}

function iniciarPrivado() {
    const nome = prompt("Nome da pessoa para conversar:");
    if (nome === null) return;
    if (!nomeValido(nome) || nome.trim() === estado.nome) {
        return avisar("Informe o nome de outra pessoa.", true);
    }
    estado.contatos.add(nome.trim());
    selecionar("privado", nome.trim());
    salvarLocal();
}

async function configurarConta() {
    if (estado.modo === "online") {
        if (!confirm("Desconectar do servidor TCP?")) return;
        try {
            await fetch("/api/disconnect", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: estado.token })
            });
        } catch (_) { /* Conexão já pode ter sido encerrada. */ }
        estado.eventos?.close();
        iniciarDemonstracao();
        avisar("Você saiu do servidor e voltou à demonstração local.");
        return;
    }
    if (estado.modo === "offline" || estado.servidorDisponivel) return abrirLogin();
    const novo = prompt("Seu nome na demonstração:", estado.nome);
    if (novo === null) return;
    if (!nomeValido(novo)) return avisar("Nome inválido.", true);
    const anterior = estado.nome;
    estado.nome = novo.trim();
    estado.usuarios.delete(anterior);
    estado.usuarios.add(estado.nome);
    Object.values(estado.participantes).forEach(membros => {
        const i = membros.indexOf(anterior);
        if (i !== -1) membros[i] = estado.nome;
    });
    Object.values(estado.conversas).forEach(mensagens => {
        mensagens.forEach(m => { if (m.de === anterior) m.de = estado.nome; });
    });
    desenharTudo();
    salvarLocal();
}

function tratarEvento(dados) {
    switch (dados.type) {
        case "USER_LIST": {
            const usuarios = Array.isArray(dados.users) ? dados.users : [];
            estado.usuarios = new Set(usuarios);
            usuarios.filter(n => n !== estado.nome).forEach(n => estado.contatos.add(n));
            break;
        }
        case "USER_STATUS": {
            if (dados.status === "online") estado.usuarios.add(dados.username);
            else estado.usuarios.delete(dados.username);
            if (dados.username !== estado.nome) estado.contatos.add(dados.username);
            break;
        }
        case "MESSAGE_RECEIVED": {
            estado.contatos.add(dados.from);
            registrarMensagem("privado", dados.from, dados.from, dados.message);
            if (estado.atual?.nome !== dados.from) avisar(`Nova mensagem de ${dados.from}`);
            return;
        }
        case "GROUP_MESSAGE_RECEIVED": {
            estado.grupos.add(dados.group);
            registrarMensagem("grupo", dados.group, dados.from, dados.message);
            if (estado.atual?.nome !== dados.group) avisar(`Nova mensagem em #${dados.group}`);
            return;
        }
        case "GROUP_LIST_RESULT": {
            estado.grupos = new Set(Array.isArray(dados.groups) ? dados.groups : []);
            break;
        }
        case "GROUP_MEMBERS_RESULT": {
            estado.participantes[dados.group] = Array.isArray(dados.members) ? dados.members : [];
            break;
        }
        case "GROUP_EVENT": {
            const p = estado.pendencia;
            if (p) {
                if (p.acao === "criar" || p.acao === "entrar") {
                    estado.grupos.add(p.grupo);
                    estado.inscritos.add(p.grupo);
                    estado.atual = { tipo: "grupo", nome: p.grupo };
                    enviarComando({ type: "GROUP_MEMBERS", group: p.grupo }).catch(() => {});
                } else if (p.acao === "sair") {
                    estado.inscritos.delete(p.grupo);
                    estado.participantes[p.grupo] = (estado.participantes[p.grupo] || [])
                        .filter(nome => nome !== estado.nome);
                }
                estado.pendencia = null;
            }
            enviarComando({ type: "GROUP_LIST" }).catch(() => {});
            avisar(dados.message || "Ação do grupo concluída.");
            break;
        }
        case "ERROR": {
            estado.pendencia = null;
            avisar(dados.message || "O servidor retornou um erro.", true);
            break;
        }
        case "CONNECTION_CLOSED": {
            estado.eventos?.close();
            estado.modo = "offline";
            avisar(dados.message || "Conexão encerrada.", true);
            break;
        }
        default: return;
    }
    desenharTudo();
}

function abrirLogin() {
    if ($( ".tela-login")) return;
    const fundo = criarElemento("div", "tela-login");
    const caixa = criarElemento("div", "caixa-login");
    const titulo = criarElemento("h2", "", "Conectar ao Concorde");
    const descricao = criarElemento("p", "", "Digite seu nome para acessar o servidor TCP.");
    const formulario = criarElemento("form");
    const campo = criarElemento("input");
    campo.type = "text";
    campo.placeholder = "Seu nome de usuário";
    campo.maxLength = 32;
    campo.required = true;
    campo.autocomplete = "nickname";
    const erro = criarElemento("p", "erro-login");
    const entrar = criarElemento("button", "botao-enviar", "Entrar no servidor");
    entrar.type = "submit";
    const demonstracao = criarElemento("button", "botao-secundario", "Usar demonstração local");
    demonstracao.type = "button";
    demonstracao.addEventListener("click", () => {
        fundo.remove();
        iniciarDemonstracao();
    });
    formulario.append(campo, erro, entrar, demonstracao);
    caixa.append(titulo, descricao, formulario);
    fundo.append(caixa);
    document.body.append(fundo);
    formulario.addEventListener("submit", async event => {
        event.preventDefault();
        const nome = campo.value.trim();
        if (!nome) return;
        entrar.disabled = true;
        erro.textContent = "";
        try {
            const resposta = await fetch("/api/connect", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: nome })
            });
            const dados = await resposta.json();
            if (!resposta.ok) throw new Error(dados.error || "Login não permitido.");
            estado.eventos?.close();
            estado.modo = "online";
            estado.nome = dados.username;
            estado.token = dados.token;
            estado.usuarios = new Set([estado.nome]);
            estado.contatos = new Set();
            estado.grupos = new Set();
            estado.inscritos = new Set();
            estado.participantes = {};
            estado.conversas = {};
            estado.atual = null;
            estado.pendencia = null;
            fundo.remove();
            estado.eventos = new EventSource(`/events?token=${encodeURIComponent(estado.token)}`);
            estado.eventos.onmessage = mensagem => {
                try { tratarEvento(JSON.parse(mensagem.data)); }
                catch (_) { avisar("Evento recebido com formato inválido.", true); }
            };
            estado.eventos.onerror = () => {
                // EventSource tenta reconectar automaticamente; aguardar evento de fechamento.
                if (estado.modo === "online") avisar("Conexão de eventos interrompida. Tentando reconectar...", true);
            };
            desenharTudo();
            await enviarComando({ type: "GROUP_LIST" });
            avisar(`Conectado como ${estado.nome}.`);
        } catch (falha) {
            erro.textContent = falha.message;
        } finally {
            entrar.disabled = false;
        }
    });
    campo.focus();
}

async function iniciar() {
    iniciarDemonstracao();
    secoes.busca.addEventListener("input", desenharLateral);
    secoes.enviar.addEventListener("click", enviarMensagem);
    secoes.entrada.addEventListener("keydown", evento => {
        if (evento.key === "Enter") {
            evento.preventDefault();
            enviarMensagem();
        }
    });
    if (location.protocol === "file:") return;
    try {
        const resposta = await fetch("/api/session", { cache: "no-store" });
        const dados = await resposta.json();
        if (resposta.ok && typeof dados.connected === "boolean") {
            estado.servidorDisponivel = true;
            abrirLogin();
        }
    } catch (_) {
        // Se não houver ponte HTTP, manter o protótipo demonstrativo.
    }
}

iniciar();
