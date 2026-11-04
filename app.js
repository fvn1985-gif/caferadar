/**
 * RADAR INVEST — Aplicação Web & Central do Investidor
 * 
 * Gerencia a navegação entre:
 * 1. Fechamento Diário (Resumo de mercado em 2 minutos)
 * 2. Swing Trade B3 (Oportunidades com alvo de +5% nas 59 ações selecionadas)
 * 3. Radar Longo Prazo (Bússola quantitativa de alocação de aportes)
 * 4. Como Usar & Filosofia
 */

(function () {
  'use strict';

  // Configuração visual de cores por classe de ativo
  const CORES_ATIVOS = {
    'Tesouro IPCA+ 2040': '#1f77b4',
    'IVVB11': '#2ca02c',
    'BOVA11': '#d62728',
    'Bitcoin': '#ff7f0e',
    'Caixa': '#7f7f7f',
    'Caixa tático': '#8c564b',
    'Caixa residual': '#7f7f7f'
  };

  /**
   * Inicialização principal
   */
  async function inicializar() {
    configurarNavegacaoAbas();
    inicializarCalculadoraRendaFixa();
    renderizarLegendaEstados();

    // Carregamento paralelo das 3 fontes de dados
    await Promise.all([
      carregarFechamentoDiario(),
      carregarSwingTrade(),
      carregarRadarAlocacao()
    ]);
  }

  // =========================================================================
  // SISTEMA DE NAVEGAÇÃO POR ABAS
  // =========================================================================

  function configurarNavegacaoAbas() {
    const botoes = document.querySelectorAll('.btn-tab[data-tab]');
    botoes.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const tabAlvo = btn.getAttribute('data-tab');
        trocarTab(tabAlvo);
      });
    });

    // Suporte a hash na URL (#fechamento, #swingtrade, #alocacao, #metodologia, #simulador)
    window.addEventListener('hashchange', aplicarHashUrl);
    window.addEventListener('load', aplicarHashUrl);
    aplicarHashUrl();
  }

  window.trocarTab = function (tabId) {
    if (!tabId) return;

    // Normaliza id caso venha com prefixo tab-
    const idLimpo = tabId.replace(/^tab-/, '');

    // Atualiza botões
    document.querySelectorAll('.btn-tab').forEach(function (btn) {
      const dt = btn.getAttribute('data-tab') || '';
      if (dt === idLimpo || dt === 'tab-' + idLimpo) {
        btn.classList.add('ativa');
      } else {
        btn.classList.remove('ativa');
      }
    });

    // Atualiza seções de conteúdo
    document.querySelectorAll('.conteudo-tab').forEach(function (sec) {
      sec.classList.remove('ativa');
    });

    const secAlvo = document.getElementById(idLimpo) || document.getElementById('tab-' + idLimpo);
    if (secAlvo) {
      secAlvo.classList.add('ativa');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Atualiza hash sem saltos na página
    if (history.pushState) {
      history.pushState(null, null, '#' + idLimpo);
    }
  };

  function aplicarHashUrl() {
    const hash = (window.location.hash || '').replace('#', '').trim();
    if (hash === 'simulador' || hash === 'calculadora' || hash === 'renda' || hash === 'tab-simulador') {
      window.trocarTab('simulador');
    } else if (hash === 'swingtrade' || hash === 'swing' || hash === 'trade' || hash === 'tab-swingtrade') {
      window.trocarTab('swingtrade');
    } else if (hash === 'alocacao' || hash === 'longoprazo' || hash === 'radar' || hash === 'tab-alocacao') {
      window.trocarTab('alocacao');
    } else if (hash === 'metodologia' || hash === 'filosofia' || hash === 'comousar' || hash === 'tab-metodologia') {
      window.trocarTab('metodologia');
    } else if (hash === 'fechamento' || hash === 'diario' || hash === 'tab-fechamento') {
      window.trocarTab('fechamento');
    }
  }

  // =========================================================================
  // CARREGAMENTO & RENDERIZAÇÃO: RADAR DE MERCADO DIÁRIO (3 EDIÇÕES)
  // =========================================================================

  let dadosFechamentoCache = null;

  async function carregarFechamentoDiario() {
    try {
      const resp = await fetch('data/fechamento.json?_t=' + Date.now(), { cache: 'no-store' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const dados = await resp.json();
      dadosFechamentoCache = dados;
      configurarBotoesEdicao(dados);
      const edicaoInicial = dados.edicao_padrao || 'fechamento';
      exibirEdicao(edicaoInicial);
    } catch (err) {
      console.warn('Usando dados de fallback para Fechamento Diário:', err.message);
      const fallback = obterFechamentoFallback();
      dadosFechamentoCache = fallback;
      configurarBotoesEdicao(fallback);
      exibirEdicao('fechamento');
    }
  }

  function configurarBotoesEdicao(dados) {
    const botoes = document.querySelectorAll('.btn-edicao');
    botoes.forEach(function (btn) {
      const idEdicao = btn.getAttribute('data-edicao');
      const ed = dados.edicoes && dados.edicoes[idEdicao];
      if (ed && ed.disponivel === false) {
        btn.classList.add('edicao-pendente');
        const horaEl = btn.querySelector('.edicao-hora');
        if (horaEl && !horaEl.textContent.includes('⏳')) {
          horaEl.textContent = '⏳ ' + (ed.horario || '');
        }
      } else if (ed && ed.disponivel === true) {
        btn.classList.remove('edicao-pendente');
        const horaEl = btn.querySelector('.edicao-hora');
        if (horaEl) {
          horaEl.textContent = ed.horario || '';
        }
      }
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        exibirEdicao(idEdicao);
      });
    });
  }

  function exibirEdicao(idEdicao) {
    if (!dadosFechamentoCache) return;

    // Atualiza botões
    document.querySelectorAll('.btn-edicao').forEach(function (btn) {
      btn.classList.remove('ativa');
      if (btn.getAttribute('data-edicao') === idEdicao) {
        btn.classList.add('ativa');
      }
    });

    let dadosEdicao = null;
    if (dadosFechamentoCache.edicoes && dadosFechamentoCache.edicoes[idEdicao]) {
      dadosEdicao = dadosFechamentoCache.edicoes[idEdicao];
    } else {
      dadosEdicao = dadosFechamentoCache;
    }

    const boxPublicada = document.getElementById('conteudo-edicao-publicada');
    const boxAguardando = document.getElementById('conteudo-edicao-aguardando');

    // Se a edição ainda não está disponível no horário de hoje
    if (dadosEdicao && dadosEdicao.disponivel === false) {
      if (boxPublicada) boxPublicada.style.display = 'none';
      if (boxAguardando) {
        boxAguardando.style.display = 'block';
        boxAguardando.innerHTML = `
          <div class="card-bloco-noticia" style="text-align:center; padding: 56px 24px; margin-top: 16px;">
            <div style="font-size: 3.2rem; margin-bottom: 14px;">⏳</div>
            <h3 style="font-size: 1.45rem; color: var(--primaria); font-weight: 800; margin-bottom: 10px;">
              Edição de ${escaparHtml(dadosEdicao.nome)} Prevista para as ${escaparHtml(dadosEdicao.horario || '12h30')}
            </h3>
            <p style="font-size: 1rem; color: var(--texto-secundario); max-width: 540px; margin: 0 auto 18px; line-height: 1.6;">
              O pregão da B3 está em andamento. A síntese, cotações consolidadas e destaques do mercado para esta edição serão publicados pontualmente às <strong>${escaparHtml(dadosEdicao.horario || '')}</strong>.
            </p>
            <div style="display:inline-block; background: var(--destaque-suave); color: var(--destaque); padding: 6px 16px; border-radius: 9999px; font-weight: 700; font-size: 0.88rem; margin-bottom: 24px;">
              ● Publicação programada: ${escaparHtml(dadosEdicao.horario || '')}
            </div>
            <div>
              <button id="btn-voltar-abertura" class="btn-tab ativa" style="padding: 10px 22px; border-radius: var(--raio-md); cursor: pointer; border: 1px solid var(--borda);">
                ← Acessar Edição de Abertura (08h30)
              </button>
            </div>
          </div>
        `;
        const btnVoltar = document.getElementById('btn-voltar-abertura');
        if (btnVoltar) {
          btnVoltar.addEventListener('click', function() {
            exibirEdicao('abertura');
          });
        }
      }
      return;
    }

    if (boxPublicada) boxPublicada.style.display = 'block';
    if (boxAguardando) boxAguardando.style.display = 'none';

    renderizarFechamento(dadosEdicao, dadosFechamentoCache.data_formatada);
  }
  window.exibirEdicao = exibirEdicao;

  function renderizarFechamento(dados, dataGeral) {
    if (!dados) return;

    const dataFinal = dataGeral || dados.data_formatada || '03/11/2026';
    const elDataBadge = document.getElementById('badge-data-fechamento');
    if (elDataBadge) elDataBadge.textContent = dataFinal;

    const elAtualizacao = document.getElementById('fechamento-atualizacao');
    if (elAtualizacao) {
      const hora = dados.horario || dados.atualizado_as || '18h30';
      const nomeEd = dados.nome ? `(${dados.nome})` : '';
      elAtualizacao.textContent = `Edição de ${dataFinal} às ${hora} ${nomeEd}`;
    }

    const elTitulo = document.getElementById('fechamento-titulo');
    if (elTitulo && dados.titulo) elTitulo.textContent = dados.titulo;

    const elSubtitulo = document.getElementById('fechamento-subtitulo');
    if (elSubtitulo && dados.subtitulo) elSubtitulo.textContent = dados.subtitulo;

    // 1. Tickers Rápidos
    const containerTickers = document.getElementById('cards-mercado-fechamento');
    if (containerTickers && dados.mercado_geral) {
      containerTickers.innerHTML = '';
      const mg = dados.mercado_geral;
      const chaves = ['ibov', 'dolar', 'sp500', 'bitcoin', 'brent'];

      chaves.forEach(function (k) {
        const item = mg[k];
        if (!item) return;
        const pos = item.positivo;
        const classeVar = pos === true ? 'positivo' : (pos === false ? 'negativo' : '');
        const seta = pos === true ? '▲' : (pos === false ? '▼' : '');
        const valExibido = item.pontos || item.valor || item.variacao;

        const card = document.createElement('div');
        card.className = 'card-ticker';
        card.innerHTML = `
          <span class="ticker-nome">${escaparHtml(item.nome)}</span>
          <span class="ticker-valor">${escaparHtml(valExibido)}</span>
          <span class="ticker-variacao ${classeVar}">${seta} ${escaparHtml(item.variacao || '')}</span>
        `;
        containerTickers.appendChild(card);
      });
    }

    // 2. Leitura Rápida
    const containerLeitura = document.getElementById('leitura-rapida-fechamento');
    if (containerLeitura && Array.isArray(dados.leitura_rapida)) {
      containerLeitura.innerHTML = '';
      dados.leitura_rapida.forEach(function (b) {
        const item = document.createElement('div');
        item.className = 'bullet-item';
        let linkHtml = '';
        if (b.link && b.fonte) {
          linkHtml = ` <a href="${escaparHtml(b.link)}" target="_blank" rel="noopener" class="link-fonte">(${escaparHtml(b.fonte)} ↗)</a>`;
        }
        item.innerHTML = `
          <span class="bullet-ponto">•</span>
          <div>${escaparHtml(b.texto)}${linkHtml}</div>
        `;
        containerLeitura.appendChild(item);
      });
    }

    // 3. Tabela Blue Chips
    const tbodyBlue = document.getElementById('tabela-blue-chips');
    if (tbodyBlue && Array.isArray(dados.acoes_blue_chips)) {
      tbodyBlue.innerHTML = '';
      dados.acoes_blue_chips.forEach(function (ac) {
        const tr = document.createElement('tr');
        const pos = ac.positivo;
        const cor = pos === true ? 'var(--alta)' : 'var(--baixa)';
        tr.innerHTML = `
          <td>
            <span class="ticker-tag">${escaparHtml(ac.ticker)}</span>
            <span class="sub-empresa">${escaparHtml(ac.nome)}</span>
          </td>
          <td class="cel-num">${escaparHtml(ac.preco)}</td>
          <td class="cel-num" style="color:${cor};font-weight:700;">${escaparHtml(ac.variacao_dia)}</td>
          <td class="cel-num" style="color:${cor};">${escaparHtml(ac.variacao_mes)}</td>
        `;
        tbodyBlue.appendChild(tr);
      });
    }

    // 4. Altas e Baixas
    const containerAltasBaixas = document.getElementById('destaques-altas-quedas');
    if (containerAltasBaixas && dados.destaques) {
      containerAltasBaixas.innerHTML = `
        <div class="coluna-altas">
          <div class="titulo-coluna-destaque alta"><span>▲</span> Maiores Altas</div>
          ${dados.destaques.altas.map(a => `
            <div class="item-destaque-ranking">
              <span class="ticker-tag">${escaparHtml(a.ticker)}</span>
              <span class="cel-num" style="color:var(--alta);font-weight:700;">${escaparHtml(a.variacao)}</span>
            </div>
          `).join('')}
        </div>
        <div class="coluna-baixas">
          <div class="titulo-coluna-destaque baixa"><span>▼</span> Maiores Quedas</div>
          ${dados.destaques.quedas.map(q => `
            <div class="item-destaque-ranking">
              <span class="ticker-tag">${escaparHtml(q.ticker)}</span>
              <span class="cel-num" style="color:var(--baixa);font-weight:700;">${escaparHtml(q.variacao)}</span>
            </div>
          `).join('')}
        </div>
      `;
    }

    // 5. Comparação Anterior
    const containerComp = document.getElementById('comparacao-anterior');
    if (containerComp && Array.isArray(dados.comparacao_anterior)) {
      containerComp.innerHTML = '';
      dados.comparacao_anterior.forEach(function (c) {
        const item = document.createElement('div');
        item.className = 'bullet-item';
        let linkHtml = '';
        if (c.link && c.fonte) {
          linkHtml = ` <a href="${escaparHtml(c.link)}" target="_blank" rel="noopener" class="link-fonte">(${escaparHtml(c.fonte)} ↗)</a>`;
        }
        item.innerHTML = `
          <span class="bullet-ponto">•</span>
          <div>${escaparHtml(c.texto)}${linkHtml}</div>
        `;
        containerComp.appendChild(item);
      });
    }
  }

  // =========================================================================
  // CARREGAMENTO & RENDERIZAÇÃO: SWING TRADE B3
  // =========================================================================

  async function carregarSwingTrade() {
    try {
      const resp = await fetch('data/swingtrade.json?_t=' + Date.now(), { cache: 'no-store' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const dados = await resp.json();
      renderizarSwingTrade(dados);
    } catch (err) {
      console.warn('Usando dados de fallback para Swing Trade:', err.message);
      renderizarSwingTrade(obterSwingFallback());
    }
  }

  function renderizarSwingTrade(dados) {
    if (!dados) return;

    // 1. Painel de Métricas do Motor
    const est = dados.estrategia || {};
    const elUni = document.getElementById('st-universo');
    if (elUni && est.universo_total) elUni.textContent = `${est.universo_total} Ações`;

    const elAlvo = document.getElementById('st-alvo');
    if (elAlvo && est.alvo_padrao_percentual) elAlvo.textContent = `+${est.alvo_padrao_percentual.toFixed(2)}%`;

    const elAssert = document.getElementById('st-assertividade');
    if (elAssert && est.assertividade_historica_1ano) elAssert.textContent = est.assertividade_historica_1ano;

    const elTempo = document.getElementById('st-tempo');
    if (elTempo && est.tempo_medio_posicao) elTempo.textContent = est.tempo_medio_posicao;

    // 2. Termômetro do Scanner Hoje
    const containerTermo = document.getElementById('st-termometro');
    if (containerTermo && dados.resumo_pregão_hoje) {
      const r = dados.resumo_pregão_hoje;
      containerTermo.innerHTML = `
        <div class="item-termometro verde">
          <div>
            <div class="termo-nome">Oportunidades Claras</div>
            <span style="font-size:0.75rem;color:var(--alta);font-weight:600;">Sinal técnico ativado</span>
          </div>
          <div class="termo-contagem" style="color:var(--alta);">${r.oportunidades || 0}</div>
        </div>
        <div class="item-termometro amarelo">
          <div>
            <div class="termo-nome">Com Ressalva</div>
            <span style="font-size:0.75rem;color:var(--alerta-indeterminado);font-weight:600;">Exige cautela</span>
          </div>
          <div class="termo-contagem" style="color:var(--alerta-indeterminado);">${r.ressalvas || 0}</div>
        </div>
        <div class="item-termometro azul">
          <div>
            <div class="termo-nome">Aguardando Gatilho</div>
            <span style="font-size:0.75rem;color:var(--destaque);font-weight:600;">Em aproximação</span>
          </div>
          <div class="termo-contagem" style="color:var(--destaque);">${r.aguardando || 0}</div>
        </div>
        <div class="item-termometro cinza">
          <div>
            <div class="termo-nome">Desfavoráveis</div>
            <span style="font-size:0.75rem;color:var(--neutro);font-weight:600;">Sem compras na queda</span>
          </div>
          <div class="termo-contagem" style="color:var(--neutro);">${r.desfavoravel || 0}</div>
        </div>
      `;
    }

    // 3. Tabela de Monitor de Oportunidades & Posições
    const tbodyST = document.getElementById('tabela-swing-trade');
    if (tbodyST && Array.isArray(dados.posicoes_destaque)) {
      tbodyST.innerHTML = '';
      dados.posicoes_destaque.forEach(function (pos) {
        const tr = document.createElement('tr');

        let badgeClasse = 'aguardar';
        let badgeTexto = pos.status_badge || 'Aguardar';

        if (pos.categoria === 'OPORTUNIDADE') {
          badgeClasse = 'oportunidade';
        } else if (pos.categoria === 'ALVO_ATINGIDO') {
          badgeClasse = 'alvo-atingido';
        } else if (pos.categoria === 'OPORTUNIDADE_COM_RESSALVA') {
          badgeClasse = 'ressalva';
        } else if (pos.categoria === 'DESFAVORAVEL') {
          badgeClasse = 'desfavoravel';
        }

        const corVar = pos.variacao_atual.includes('-') ? 'var(--baixa)' : (pos.variacao_atual === '—' ? 'inherit' : 'var(--alta)');

        tr.innerHTML = `
          <td>
            <span class="ticker-tag">${escaparHtml(pos.ticker)}</span>
            <span class="sub-empresa">${escaparHtml(pos.empresa)}</span>
          </td>
          <td style="font-size:0.85rem;">${escaparHtml(pos.setup)}</td>
          <td class="cel-num">${escaparHtml(pos.preco_entrada)}</td>
          <td class="cel-num" style="color:var(--destaque);font-weight:700;">${escaparHtml(pos.alvo_saida)}</td>
          <td class="cel-num" style="color:${corVar};font-weight:700;">${escaparHtml(pos.variacao_atual)}</td>
          <td><span class="badge-swing ${badgeClasse}">${escaparHtml(badgeTexto)}</span></td>
        `;
        tbodyST.appendChild(tr);
      });
    }

    // 4. As 3 Regras de Ouro
    const containerRegras = document.getElementById('st-regras');
    if (containerRegras && Array.isArray(dados.principais_regras_simples)) {
      containerRegras.innerHTML = '';
      dados.principais_regras_simples.forEach(function (regra) {
        const card = document.createElement('div');
        card.className = 'card-humano';
        card.innerHTML = `
          <div class="card-humano-header" style="border-left-color: var(--alta);">
            <h4>${escaparHtml(regra.titulo)}</h4>
          </div>
          <p>${escaparHtml(regra.descricao)}</p>
        `;
        containerRegras.appendChild(card);
      });
    }
  }

  // =========================================================================
  // CARREGAMENTO & RENDERIZAÇÃO: RADAR LONGO PRAZO
  // =========================================================================

  async function carregarRadarAlocacao() {
    try {
      const resp = await fetch('data/dashboard.json?_t=' + Date.now(), { cache: 'no-store' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const dados = await resp.json();
      renderizarRadar(dados, false);
    } catch (err) {
      console.warn('Usando dados de fallback para Radar Longo Prazo:', err.message);
      renderizarRadar(obterRadarFallback(), true);
    }
  }

  function renderizarRadar(dados, isDemo) {
    if (!dados) return;

    renderizarExecucao(dados, isDemo);
    renderizarAlocacao(dados.allocation, dados.eligibility, dados.allocation_blocked);
    renderizarIndicadoresOficiais(dados.indicators);
    renderizarAlertasOficiais(dados.alerts);
    renderizarJustificativas(dados.allocation_rationale, dados.warnings);
    renderizarHistoricoOficial(dados);
  }

  function renderizarExecucao(dados, isDemo) {
    const elData = document.getElementById('data-referencia');
    const elEstado = document.getElementById('estado-execucao');
    const elAviso = document.getElementById('aviso-demo');
    const elBanner = document.querySelector('.banner-demo');

    const dataRef = dados.reference_date || (dados.generated_at ? dados.generated_at.split('T')[0] : '—');
    if (elData) elData.textContent = formatarData(dataRef);
    if (elEstado) elEstado.textContent = dados.status || 'CONCLUÍDO';

    if (isDemo) {
      if (elAviso) elAviso.textContent = 'Modo de visualização local offline (dados demonstrativos).';
      if (elBanner) elBanner.innerHTML = '<strong>PROTÓTIPO — DADOS DEMONSTRATIVOS</strong>';
    } else {
      if (elAviso) {
        elAviso.textContent = 'Relatório quantitativo oficial gerado pelo motor Python (' + formatarData(dataRef) + '). Alocação calculada para o novo aporte do mês.';
      }
      if (elBanner) {
        elBanner.innerHTML = '<strong>RELATÓRIO OFICIAL DO RADAR (REFERÊNCIA: ' + formatarData(dataRef) + ') — MOTOR PYTHON v' + (dados.app_version || '0.3.0') + '</strong>';
      }
    }
  }

  function renderizarAlocacao(alocacao, elegibilidade, bloqueado) {
    const containerLista = document.getElementById('lista-alocacao');
    const containerGrafico = document.getElementById('grafico-pizza');

    if (!containerLista) return;
    containerLista.innerHTML = '';

    if (bloqueado || !alocacao) {
      containerLista.innerHTML = '<div class="aviso-execucao" style="background:#fee2e2;color:#991b1b;"><strong>ALOCAÇÃO BLOQUEADA PELO MOTOR:</strong> O motor suspendeu preventivamente a recomendação por inconsistência nos dados de mercado.</div>';
      if (containerGrafico) containerGrafico.innerHTML = '<p style="color:#991b1b;font-weight:700;">Alocação Suspensa</p>';
      return;
    }

    const tatico = Number(alocacao['Caixa tático'] ?? alocacao['Caixa tatico'] ?? 0);
    const residual = Number(alocacao['Caixa residual'] ?? 0);
    const totalCaixa = tatico + residual;

    const itens = [
      { nome: 'Tesouro IPCA+ 2040', perc: alocacao['Tesouro IPCA+ 2040'], chaveEleg: 'Tesouro IPCA+ 2040' },
      { nome: 'IVVB11', perc: alocacao['IVVB11'], chaveEleg: 'IVVB11' },
      { nome: 'BOVA11', perc: alocacao['BOVA11'], chaveEleg: 'BOVA11' },
      { nome: 'Bitcoin', perc: alocacao['Bitcoin'], chaveEleg: 'Bitcoin' },
      { nome: 'Caixa', perc: totalCaixa, chaveEleg: 'Caixa', detalhe: 'Tático: ' + tatico + '% | Residual: ' + residual + '%' }
    ];

    itens.forEach(function (item) {
      const valorPerc = item.perc !== null && item.perc !== undefined ? Number(item.perc) : null;
      const textoPerc = valorPerc !== null ? valorPerc + '%' : '—';
      const cor = CORES_ATIVOS[item.nome] || '#1f4e79';

      let textoEleg = 'Elegível';
      if (elegibilidade && elegibilidade[item.chaveEleg] === false) {
        textoEleg = 'Inelegível / Veto';
      }

      const card = document.createElement('div');
      card.className = 'card-atributo';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h3 style="font-size:1rem;font-weight:700;">${escaparHtml(item.nome)}</h3>
          <span style="font-size:0.8rem;color:${textoEleg.includes('Veto') ? 'var(--baixa)' : 'var(--alta)'};font-weight:700;">${textoEleg}</span>
        </div>
        <div class="percentual-destaque" style="color:${cor};">${textoPerc}</div>
        <div class="barra-alocacao">
          <div class="barra-preenchimento" style="width:${valorPerc || 0}%;background-color:${cor};"></div>
        </div>
        ${item.detalhe ? `<span class="rotulo-exemplo">${escaparHtml(item.detalhe)}</span>` : ''}
      `;
      containerLista.appendChild(card);
    });

    if (containerGrafico) {
      renderizarGraficoPizza(itens, containerGrafico);
    }
  }

  function renderizarGraficoPizza(itens, container) {
    let acumulado = 0;
    const fatias = [];
    const itensValidos = itens.filter(i => Number(i.perc) > 0);

    itensValidos.forEach(function (item) {
      const perc = Number(item.perc);
      const cor = CORES_ATIVOS[item.nome] || '#333';
      const inicio = acumulado;
      acumulado += perc;
      fatias.push({ nome: item.nome, perc: perc, cor: cor, inicio: inicio, fim: acumulado });
    });

    let svgContent = '';
    if (itensValidos.length === 0) {
      svgContent = '<circle cx="50" cy="50" r="40" fill="none" stroke="#e0e0e0" stroke-width="18"/>';
    } else {
      fatias.forEach(function (f) {
        const strokeDash = `${f.perc} ${100 - f.perc}`;
        const strokeOffset = 25 - f.inicio;
        svgContent += `
          <circle cx="50" cy="50" r="25" fill="transparent"
                  stroke="${f.cor}" stroke-width="20"
                  stroke-dasharray="${strokeDash}"
                  stroke-dashoffset="${strokeOffset}"
                  pathLength="100"/>
        `;
      });
    }

    let legendaHtml = '<div class="legenda-pizza" style="display:flex;flex-wrap:wrap;gap:10px;margin-top:16px;justify-content:center;">';
    itens.forEach(function (item) {
      const p = item.perc !== null && item.perc !== undefined ? item.perc + '%' : '—';
      const cor = CORES_ATIVOS[item.nome] || '#333';
      legendaHtml += `
        <div class="legenda-item" style="display:inline-flex;align-items:center;font-size:0.85rem;">
          <span style="display:inline-block;width:12px;height:12px;background:${cor};border-radius:3px;margin-right:6px;"></span>
          <span><strong>${escaparHtml(item.nome)}:</strong> ${p}</span>
        </div>
      `;
    });
    legendaHtml += '</div>';

    container.innerHTML = `
      <svg viewBox="0 0 100 100" class="grafico-pizza" style="border-radius:50%; width:160px; height:160px;">
        ${svgContent}
      </svg>
      ${legendaHtml}
    `;
  }

  function renderizarIndicadoresOficiais(ind) {
    const tbody = document.getElementById('tabela-indicadores');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!ind || typeof ind !== 'object') {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:16px;">Nenhum indicador disponível.</td></tr>';
      return;
    }

    const lista = [];

    if (ind.ibov) {
      const v = ind.ibov.last_close ? formatarMoeda(ind.ibov.last_close.value, 2) : '—';
      const sma = ind.ibov.sma200 ? 'SMA200: ' + formatarNumero(ind.ibov.sma200.value, 0) : '—';
      const data = ind.ibov.last_close ? formatarData(ind.ibov.last_close.date) : '—';
      const idade = ind.ibov.last_close_age_calendar_days !== null ? ' (' + ind.ibov.last_close_age_calendar_days + 'd)' : '';
      lista.push({ nome: 'Ibovespa', valor: v, var: sma, fonte: 'Ipeadata OData (B3)', atualizacao: data + idade, valido: ind.ibov.valid });
    }

    if (ind.ptax_venda) {
      const v = ind.ptax_venda.last_sale ? 'R$ ' + formatarNumero(ind.ptax_venda.last_sale.value, 4) : '—';
      const sma = ind.ptax_venda.sma200 ? 'SMA200: ' + formatarNumero(ind.ptax_venda.sma200.value, 4) : '—';
      const data = ind.ptax_venda.last_sale ? formatarData(ind.ptax_venda.last_sale.date) : '—';
      lista.push({ nome: 'Dólar PTAX Venda', valor: v, var: sma, fonte: 'Banco Central (Olinda PTAX)', atualizacao: data, valido: ind.ptax_venda.valid });
    }

    if (ind.tesouro_ipca2040) {
      const taxa = ind.tesouro_ipca2040.last_buy_rate_percent !== null ? formatarNumero(ind.tesouro_ipca2040.last_buy_rate_percent, 2) + '% a.a.' : '—';
      const data = ind.tesouro_ipca2040.date ? formatarData(ind.tesouro_ipca2040.date) : '—';
      lista.push({ nome: 'Tesouro IPCA+ 2040', valor: taxa, var: 'Limiar: >= 6,50% a.a.', fonte: ind.tesouro_ipca2040.manual_entry ? 'Entrada manual declarada' : 'Tesouro Direto', atualizacao: data, valido: ind.tesouro_ipca2040.valid });
    }

    if (ind.di1_stress) {
      const ativo = ind.di1_stress.active;
      const statusTxt = ativo === true ? 'Estresse ATIVO' : (ativo === false ? 'Normal (Inativo)' : 'Indeterminado');
      const limiar = ind.di1_stress.threshold_bps !== null ? 'Limiar: ' + ind.di1_stress.threshold_bps + ' bps' : '—';
      lista.push({ nome: 'DI1 (estresse soberano)', valor: statusTxt, var: limiar, fonte: 'PYield / B3', atualizacao: 'Data do pregão', valido: ind.di1_stress.valid });
    }

    if (ind.cds_brazil_5y) {
      const v = ind.cds_brazil_5y.value_bps !== null ? formatarNumero(ind.cds_brazil_5y.value_bps, 2) + ' bps' : '—';
      const limiar = ind.cds_brazil_5y.threshold_bps !== null ? 'Limiar: ' + ind.cds_brazil_5y.threshold_bps + ' bps' : '—';
      lista.push({ nome: 'CDS Brasil 5Y', valor: v, var: limiar, fonte: 'Entrada manual autorizada', atualizacao: 'Data do pregão', valido: ind.cds_brazil_5y.valid });
    }

    if (ind.bitcoin) {
      const v = ind.bitcoin.last_close ? formatarMoeda(ind.bitcoin.last_close.value, 2) + ' USD' : '—';
      const dd = ind.bitcoin.drawdown_from_high_percent !== null ? 'DD 365d: ' + formatarNumero(ind.bitcoin.drawdown_from_high_percent, 2) + '%' : '—';
      const data = ind.bitcoin.last_close ? formatarData(ind.bitcoin.last_close.date) : '—';
      lista.push({ nome: 'Bitcoin (BTCUSDT)', valor: v, var: dd, fonte: 'Binance Spot API (UTC)', atualizacao: data, valido: ind.bitcoin.valid });
    }

    if (ind.erp_real_regra_radar) {
      const v = ind.erp_real_regra_radar.value_percent !== null ? formatarNumero(ind.erp_real_regra_radar.value_percent, 3) + '%' : '—';
      const data = ind.erp_real_regra_radar.date ? formatarData(ind.erp_real_regra_radar.date) : '—';
      lista.push({ nome: 'ERP (regra do Radar)', valor: v, var: 'Earnings Yield - Tesouro', fonte: 'Cálculo homologado do Radar', atualizacao: data, valido: ind.erp_real_regra_radar.valid });
    }

    lista.forEach(function (item) {
      const tr = document.createElement('tr');
      let badgeHtml = '<span class="badge-status status-desatualizado">Pendente</span>';
      if (item.valido === true) badgeHtml = '<span class="badge-status status-valido">Válido</span>';
      else if (item.valido === false) badgeHtml = '<span class="badge-status status-invalido">Inválido</span>';

      tr.innerHTML = `
        <td><strong>${escaparHtml(item.nome)}</strong></td>
        <td class="cel-valor">${escaparHtml(item.valor)}</td>
        <td>${escaparHtml(item.var)}</td>
        <td>${escaparHtml(item.fonte)}</td>
        <td>${escaparHtml(item.atualizacao)}</td>
        <td>${badgeHtml}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderizarAlertasOficiais(alerts) {
    const container = document.getElementById('lista-alertas');
    if (!container) return;
    container.innerHTML = '';

    const defs = [
      { id: 'alert1_ibov_stretch', titulo: 'Alerta 1 — Esticamento do Ibovespa', desc: 'Sinaliza se o Ibovespa se afastou excessivamente de sua média móvel de 200 períodos (SMA200).' },
      { id: 'alert2_sovereign_stress', titulo: 'Alerta 2 — Estresse Soberano', desc: 'Combinação de abertura nas taxas de juros futuros (DI1) e spread de risco país (CDS Brasil 5Y).' },
      { id: 'alert3_systemic_rupture', titulo: 'Alerta 3 — Ruptura Sistêmica', desc: 'Condição extrema em múltiplos mercados que impõe retenção defensiva máxima em caixa e ativos de proteção.' }
    ];

    defs.forEach(function (def) {
      const estadoValor = alerts ? alerts[def.id] : null;
      let badgeClass = 'badge-alerta-inativo';
      let badgeTexto = 'Inativo';

      if (estadoValor === true) {
        badgeClass = 'badge-alerta-ativo';
        badgeTexto = 'Ativo';
      } else if (estadoValor === null || estadoValor === undefined) {
        badgeClass = 'badge-alerta-indeterminado';
        badgeTexto = 'Indeterminado';
      }

      const card = document.createElement('div');
      card.className = 'card-alerta';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h4>${escaparHtml(def.titulo)}</h4>
          <span class="${badgeClass}">${badgeTexto}</span>
        </div>
        <p class="desc-alerta">${escaparHtml(def.desc)}</p>
      `;
      container.appendChild(card);
    });
  }

  function renderizarJustificativas(rationale, warnings) {
    const containerJust = document.getElementById('lista-justificativas');
    const containerAvisos = document.getElementById('lista-avisos');

    if (containerJust) {
      containerJust.innerHTML = '';
      if (rationale && typeof rationale === 'object') {
        Object.entries(rationale).forEach(function ([ativo, texto]) {
          const card = document.createElement('div');
          card.className = 'card-justificativa';
          card.innerHTML = `
            <strong>${escaparHtml(ativo)}</strong>
            <p style="margin:0;color:var(--texto-secundario);">${escaparHtml(texto)}</p>
          `;
          containerJust.appendChild(card);
        });
      }
    }

    if (containerAvisos) {
      containerAvisos.innerHTML = '';
      if (Array.isArray(warnings) && warnings.length > 0) {
        const div = document.createElement('div');
        div.className = 'aviso-dados';
        let itens = '';
        warnings.forEach(function (w) {
          itens += `<li>${escaparHtml(w)}</li>`;
        });
        div.innerHTML = `
          <strong>Avisos e Notas de Governança do Motor:</strong>
          <ul style="margin:8px 0 0 20px;padding:0;">${itens}</ul>
        `;
        containerAvisos.appendChild(div);
      }
    }
  }

  function renderizarHistoricoOficial(dados) {
    const tbody = document.getElementById('lista-historico');
    if (!tbody) return;
    tbody.innerHTML = '';

    const dataRef = dados.reference_date || (dados.generated_at ? dados.generated_at.split('T')[0] : '—');
    const status = dados.status || 'Executado';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escaparHtml(formatarData(dataRef))}</strong></td>
      <td><span class="badge-historico-sucesso">${escaparHtml(status)}</span></td>
      <td><span style="font-size:0.85rem;color:var(--texto-mutado);">Execução Homologada (v${escaparHtml(dados.app_version || '0.3.0')})</span></td>
    `;
    tbody.appendChild(tr);
  }

  function renderizarLegendaEstados() {
    const container = document.getElementById('legenda-estados');
    if (!container) return;
    container.innerHTML = `
      <span style="font-size:0.8rem;color:var(--texto-mutado);margin-right:8px;">Legenda de Auditoria:</span>
      <span class="badge-status status-valido" style="margin-right:8px;">Válido</span>
      <span class="badge-status status-desatualizado" style="margin-right:8px;">Desatualizado / Pendente</span>
      <span class="badge-status status-invalido">Inválido / Rejeitado</span>
    `;
  }

  // =========================================================================
  // DADOS DE FALLBACK (OFFLINE)
  // =========================================================================

  function obterFechamentoFallback() {
    return {
      data_formatada: '03/11/2026',
      titulo: 'RADAR DE FECHAMENTO — 03/11/2026',
      subtitulo: 'Ibov recua 1,35% com cautela fiscal pré-Copom; Dólar vai a R$ 5,49',
      atualizado_as: '18h30',
      mercado_geral: {
        ibov: { nome: 'Ibovespa', pontos: '165.659', variacao: '-1,35%', positivo: false },
        dolar: { nome: 'Dólar Comercial', valor: 'R$ 5,49', variacao: '+0,95%', positivo: true },
        sp500: { nome: 'S&P 500', variacao: '+0,36%', positivo: true },
        bitcoin: { nome: 'Bitcoin', valor: 'US$ 77.798', variacao: '+1,32%', positivo: true },
        brent: { nome: 'Petróleo Brent', valor: 'US$ 106,52', variacao: '+1,67%', positivo: true }
      },
      acoes_blue_chips: [
        { ticker: 'PETR4', nome: 'Petrobras PN', preco: 'R$ 50,71', variacao_dia: '-3,79%', variacao_mes: '-3,79%', positivo: false },
        { ticker: 'VALE3', nome: 'Vale ON', preco: 'R$ 60,25', variacao_dia: '-2,85%', variacao_mes: '-2,85%', positivo: false },
        { ticker: 'ITUB4', nome: 'Itaú PN', preco: 'R$ 38,49', variacao_dia: '-0,52%', variacao_mes: '-0,52%', positivo: false },
        { ticker: 'WEGE3', nome: 'WEG ON', preco: 'R$ 49,17', variacao_dia: '+1,67%', variacao_mes: '+1,67%', positivo: true }
      ],
      destaques: {
        altas: [{ ticker: 'EMBJ3', variacao: '+3,72%' }, { ticker: 'TIMS3', variacao: '+3,23%' }],
        quedas: [{ ticker: 'COGN3', variacao: '-10,76%' }, { ticker: 'CMIN3', variacao: '-5,56%' }]
      },
      leitura_rapida: [
        { texto: 'O Ibovespa caiu 1,35%, fechando aos 165.659 pontos na volta do feriado de Finados acumulando perdas pré-Copom.' },
        { texto: 'Dólar comercial subiu a R$ 5,49 com pressão nos juros futuros após projeções de alta da Selic no Focus.' }
      ],
      comparacao_anterior: [
        { texto: 'Bolsa estendeu trajetória de baixa e perdeu mais de 2.200 pontos em relação ao fechamento anterior.' }
      ]
    };
  }

  function obterSwingFallback() {
    return {
      estrategia: {
        universo_total: 59,
        alvo_padrao_percentual: 5.0,
        assertividade_historica_1ano: '89,0%',
        tempo_medio_posicao: '6 a 12 dias'
      },
      resumo_pregão_hoje: { oportunidades: 1, ressalvas: 1, aguardando: 14, desfavoravel: 43 },
      posicoes_destaque: [
        { ticker: 'WEGE3', empresa: 'WEG S.A.', setup: 'Força Relativa', preco_entrada: 'R$ 48,35', alvo_saida: 'R$ 50,77 (+5%)', variacao_atual: '+1,67%', categoria: 'OPORTUNIDADE', status_badge: 'Em Andamento' },
        { ticker: 'BBSE3', empresa: 'BB Seguridade', setup: 'Reversão Suporte', preco_entrada: 'R$ 34,20', alvo_saida: 'R$ 35,91 (+5%)', variacao_atual: '+5,00%', categoria: 'ALVO_ATINGIDO', status_badge: 'Alvo Batido' }
      ],
      principais_regras_simples: [
        { titulo: '1. Apenas 59 Melhores Ações', descricao: 'Sem empresas falidas ou micos da bolsa.' },
        { titulo: '2. Alvo Fixo de +5%', descricao: 'Bateu a meta, lucro no bolso.' },
        { titulo: '3. Disciplina na Queda', descricao: 'Não compra faca caindo.' }
      ]
    };
  }

  function obterRadarFallback() {
    return {
      reference_date: '2026-10-23',
      status: 'DEMONSTRAÇÃO',
      allocation: { 'Tesouro IPCA+ 2040': 60, 'IVVB11': 30, 'BOVA11': 0, 'Bitcoin': 10, 'Caixa': 0 },
      eligibility: { 'Tesouro IPCA+ 2040': true, 'IVVB11': true, 'BOVA11': false, 'Bitcoin': true, 'Caixa': true },
      allocation_blocked: false,
      indicators: {},
      alerts: { alert1_ibov_stretch: false, alert2_sovereign_stress: false, alert3_systemic_rupture: false },
      allocation_rationale: { 'Tesouro IPCA+ 2040': 'Prioridade para taxas acima de 6,50% a.a.' },
      warnings: ['Visualização em contingência.']
    };
  }

  // --- Funções Auxiliares de Formatação e Segurança ---

  function escaparHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatarData(iso) {
    if (!iso || typeof iso !== 'string') return '—';
    const partes = iso.split('T')[0].split('-');
    if (partes.length === 3) return partes[2] + '/' + partes[1] + '/' + partes[0];
    return iso;
  }

  function formatarNumero(num, decimais) {
    if (num === null || num === undefined || isNaN(num)) return '—';
    return Number(num).toLocaleString('pt-BR', {
      minimumFractionDigits: decimais !== undefined ? decimais : 2,
      maximumFractionDigits: decimais !== undefined ? decimais : 2
    });
  }

  function formatarMoeda(num, decimais) {
    if (num === null || num === undefined || isNaN(num)) return '—';
    return Number(num).toLocaleString('pt-BR', {
      minimumFractionDigits: decimais !== undefined ? decimais : 2,
      maximumFractionDigits: decimais !== undefined ? decimais : 2
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializar);
  } else {
    inicializar();
  }

})();

  // =========================================================================
  // CALCULADORA DE RENDA FIXA INTERATIVA (TRÁFEGO ETERNO & BACKLINKS)
  // =========================================================================

  function inicializarCalculadoraRendaFixa() {
    const inputValor = document.getElementById('calc-valor');
    if (!inputValor) return;

    let mesesSelecionados = 12;

    function calcular() {
      const valor = parseFloat(inputValor.value) || 0;
      if (valor <= 0) return;

      // Taxas atuais de mercado
      const selicAnual = 0.1125; // 11,25% a.a.
      const cdiAnual = 0.1115;   // 11,15% a.a.
      const poupancaAnual = 0.0617; // 6,17% a.a. (0,5% a.m. + TR)

      let dias = mesesSelecionados * 30;
      if (mesesSelecionados === 12) dias = 365;
      else if (mesesSelecionados === 24) dias = 730;
      else if (mesesSelecionados === 36) dias = 1095;

      let aliquotaIR = 0.225; // até 180 dias
      if (dias > 180 && dias <= 360) aliquotaIR = 0.20;
      else if (dias > 360 && dias <= 720) aliquotaIR = 0.175;
      else if (dias > 720) aliquotaIR = 0.15;

      const anos = mesesSelecionados / 12.0;

      // 1. Poupança (Isenta de IR)
      const totalPoupanca = valor * Math.pow(1 + poupancaAnual, anos);
      const lucroPoupanca = totalPoupanca - valor;

      // 2. CDB 100% do CDI (com desconto de IR)
      const brutoCDI = valor * Math.pow(1 + cdiAnual, anos);
      const lucroBrutoCDI = brutoCDI - valor;
      const irCDI = lucroBrutoCDI * aliquotaIR;
      const lucroLiqCDI = lucroBrutoCDI - irCDI;
      const totalCDI = valor + lucroLiqCDI;

      // 3. Tesouro Selic (Selic + 0,05% a.a., com IR)
      const taxaSelicEfetiva = selicAnual + 0.0005;
      const brutoSelic = valor * Math.pow(1 + taxaSelicEfetiva, anos);
      const lucroBrutoSelic = brutoSelic - valor;
      const irSelic = lucroBrutoSelic * aliquotaIR;
      const lucroLiqSelic = lucroBrutoSelic - irSelic;
      const totalSelic = valor + lucroLiqSelic;

      function fmt(val) {
        return 'R$ ' + val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      }

      document.getElementById('res-total-poupanca').textContent = fmt(totalPoupanca);
      document.getElementById('res-lucro-poupanca').textContent = '+' + fmt(lucroPoupanca);

      document.getElementById('res-total-cdi').textContent = fmt(totalCDI);
      document.getElementById('res-lucro-cdi').textContent = '+' + fmt(lucroLiqCDI);

      document.getElementById('res-total-selic').textContent = fmt(totalSelic);
      document.getElementById('res-lucro-selic').textContent = '+' + fmt(lucroLiqSelic);

      const diff = lucroLiqSelic - lucroPoupanca;
      const elDiff = document.getElementById('diferenca-lucro-reais');
      if (elDiff) {
        elDiff.textContent = fmt(diff) + ' a MAIS';
      }
    }

    inputValor.addEventListener('input', calcular);

    // Chips de valores rápidos
    document.querySelectorAll('.btn-chip').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelectorAll('.btn-chip').forEach(b => b.classList.remove('ativa'));
        btn.classList.add('ativa');
        inputValor.value = btn.getAttribute('data-val');
        calcular();
      });
    });

    // Botões de prazos
    document.querySelectorAll('.btn-prazo').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelectorAll('.btn-prazo').forEach(b => b.classList.remove('ativa'));
        btn.classList.add('ativa');
        mesesSelecionados = parseInt(btn.getAttribute('data-meses'), 10) || 12;
        calcular();
      });
    });

    calcular();
  }
