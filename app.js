/**
 * CAFERADAR — Aplicação Web & Central do Investidor
 *
 * Gerencia a navegação entre:
 * 1. Fechamento Diário (Síntese do pregão da B3)
 * 2. Swing Trade B3 (Scanner quantitativo sobre 59 ações)
 * 3. Radar Longo Prazo (Estudo quantitativo de alocação)
 * 4. Simulador de Renda Fixa & Filosofia
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

  let abaAtual = 'fechamento';

  // Calendário de feriados conhecidos da B3 (espelha src/engine.py::_b3_holidays)
  function pascoaGregoriana(ano) {
    const a = ano % 19;
    const b = Math.floor(ano / 100);
    const c = ano % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const mes = Math.floor((h + l - 7 * m + 114) / 31);
    const dia = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(Date.UTC(ano, mes - 1, dia));
  }

  function somarDiasUTC(dt, dias) {
    return new Date(dt.getTime() + dias * 86400000);
  }

  function fmtIsoUTC(dt) {
    const y = dt.getUTCFullYear();
    const m = String(dt.getUTCMonth() + 1).padStart(2, '0');
    const d = String(dt.getUTCDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  const cacheFeriadosB3 = {};
  function obterFeriadosB3(ano) {
    if (cacheFeriadosB3[ano]) return cacheFeriadosB3[ano];
    const pascoa = pascoaGregoriana(ano);
    const set = new Set([
      `${ano}-01-01`,
      fmtIsoUTC(somarDiasUTC(pascoa, -48)),
      fmtIsoUTC(somarDiasUTC(pascoa, -47)),
      fmtIsoUTC(somarDiasUTC(pascoa, -2)),
      `${ano}-04-21`,
      `${ano}-05-01`,
      fmtIsoUTC(somarDiasUTC(pascoa, 60)),
      `${ano}-09-07`,
      `${ano}-10-12`,
      `${ano}-11-02`,
      `${ano}-11-15`,
      `${ano}-12-24`,
      `${ano}-12-25`,
      `${ano}-12-31`
    ]);
    if (ano >= 2024) set.add(`${ano}-11-20`);
    cacheFeriadosB3[ano] = set;
    return set;
  }

  function ehDiaPregaoB3(dtUtc) {
    const dow = dtUtc.getUTCDay();
    if (dow === 0 || dow === 6) return false;
    const iso = fmtIsoUTC(dtUtc);
    return !obterFeriadosB3(dtUtc.getUTCFullYear()).has(iso);
  }

  function obterAgoraSaoPaulo() {
    const agora = new Date();
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Sao_Paulo',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).formatToParts(agora);
    const map = {};
    parts.forEach(function (p) { map[p.type] = p.value; });
    const dataIso = `${map.year}-${map.month}-${map.day}`;
    const hora = parseInt(map.hour || '0', 10) % 24;
    const minuto = parseInt(map.minute || '0', 10);
    const dtUtc = new Date(Date.UTC(Number(map.year), Number(map.month) - 1, Number(map.day)));
    return { dataIso: dataIso, hora: hora, minuto: minuto, totalMin: hora * 60 + minuto, dtUtc: dtUtc };
  }

  function atualizarBadgeStatusMercado() {
    const badge = document.getElementById('badge-status-mercado');
    const txt = document.getElementById('texto-status-mercado');
    if (!badge || !txt) return;
    try {
      const sp = obterAgoraSaoPaulo();
      const dow = sp.dtUtc.getUTCDay();
      const ehFds = (dow === 0 || dow === 6);
      const pregaoDia = ehDiaPregaoB3(sp.dtUtc);
      const emHorarioPregao = pregaoDia && sp.totalMin >= (10 * 60) && sp.totalMin < (17 * 60 + 55);
      const dot = badge.querySelector('.bolinha-pulso');
      if (emHorarioPregao) {
        badge.classList.remove('fechado');
        badge.classList.add('aberto');
        if (dot) dot.classList.add('ativa');
        txt.textContent = 'Pregão B3 Aberto';
      } else {
        badge.classList.add('fechado');
        badge.classList.remove('aberto');
        if (dot) dot.classList.remove('ativa');
        if (ehFds) {
          txt.textContent = 'Pregão B3 Fechado (Fim de Semana)';
        } else if (!pregaoDia) {
          txt.textContent = 'Pregão B3 Fechado (Feriado)';
        } else {
          txt.textContent = 'Pregão B3 Fechado';
        }
      }
    } catch (e) {
      txt.textContent = 'Pregão B3';
    }
  }

  function atualizarConsentimentoGtag(concedido) {
    const estado = concedido ? 'granted' : 'denied';
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      'event': 'consent_update',
      'ad_storage': estado,
      'analytics_storage': estado,
      'ad_user_data': estado,
      'ad_personalization': estado
    });
    if (typeof window.gtag === 'function') {
      window.gtag('consent', 'update', {
        'ad_storage': estado,
        'analytics_storage': estado,
        'ad_user_data': estado,
        'ad_personalization': estado
      });
    }
    console.log('[Consent Mode v2] Status atualizado no Google Tag Manager / GA4:', estado.toUpperCase());
  }

  function inicializarBannerCookies() {
    const banner = document.getElementById('banner-cookies-lgpd');
    const btnAceitar = document.getElementById('btn-aceitar-cookies');
    const btnRecusar = document.getElementById('btn-recusar-cookies');
    const linkGerenciar = document.getElementById('link-gerenciar-cookies');

    if (linkGerenciar) {
      linkGerenciar.addEventListener('click', function (e) {
        e.preventDefault();
        try { localStorage.removeItem('caferadar_cookies_ack'); } catch (err) {}
        if (banner) {
          banner.style.display = 'flex';
        }
      });
    }

    try {
      const ack = localStorage.getItem('caferadar_cookies_ack');
      if (ack === 'true') {
        atualizarConsentimentoGtag(true);
        if (banner) banner.style.display = 'none';
        return;
      } else if (ack === 'false') {
        atualizarConsentimentoGtag(false);
        if (banner) banner.style.display = 'none';
        return;
      }
      if (banner) banner.style.display = 'flex';
      if (btnAceitar) {
        btnAceitar.addEventListener('click', function () {
          try { localStorage.setItem('caferadar_cookies_ack', 'true'); } catch (e) {}
          atualizarConsentimentoGtag(true);
          if (banner) banner.style.display = 'none';
        });
      }
      if (btnRecusar) {
        btnRecusar.addEventListener('click', function () {
          try { localStorage.setItem('caferadar_cookies_ack', 'false'); } catch (e) {}
          atualizarConsentimentoGtag(false);
          if (banner) banner.style.display = 'none';
        });
      }
    } catch (e) {
      if (banner) banner.style.display = 'none';
    }
  }

  /**
   * Inicialização principal
   */
  async function inicializar() {
    atualizarBadgeStatusMercado();
    configurarNavegacaoAbas();
    inicializarCalculadoraRendaFixa();
    inicializarBannerCookies();
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
    const botoes = Array.from(document.querySelectorAll('.btn-tab[data-tab]'));
    botoes.forEach(function (btn, idx) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const tabAlvo = btn.getAttribute('data-tab');
        trocarTab(tabAlvo);
      });
      btn.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
          e.preventDefault();
          const dir = e.key === 'ArrowRight' ? 1 : -1;
          const next = botoes[(idx + dir + botoes.length) % botoes.length];
          if (next) {
            next.focus();
            trocarTab(next.getAttribute('data-tab'));
          }
        }
      });
    });

    // Suporte a hash na URL (#fechamento, #swingtrade, #alocacao, #metodologia, #simulador)
    window.addEventListener('hashchange', aplicarHashUrl);
    aplicarHashUrl();
    inicializarAnunciosAdSense();
  }


  // Controle de Ciência Regulatória e Consentimento Informado (CVM 19 e 20)
  function fecharModaisGovernanca() {
    const mSwing = document.getElementById('modal-governanca-swing');
    const mAloc = document.getElementById('modal-governanca-alocacao');
    if (mSwing) mSwing.style.display = 'none';
    if (mAloc) mAloc.style.display = 'none';
  }

  function cancelarModalConsentimento() {
    fecharModaisGovernanca();
    const destino = (abaAtual && abaAtual !== 'swingtrade' && abaAtual !== 'alocacao') ? abaAtual : 'fechamento';
    if (window.location.hash && window.location.hash !== '#' + destino) {
      if (history.replaceState) {
        history.replaceState(null, null, '#' + destino);
      }
    }
    const btnFoco = document.querySelector(`.btn-tab[data-tab="${destino}"]`);
    if (btnFoco) btnFoco.focus();
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const mSwing = document.getElementById('modal-governanca-swing');
      const mAloc = document.getElementById('modal-governanca-alocacao');
      if ((mSwing && mSwing.style.display === 'flex') || (mAloc && mAloc.style.display === 'flex')) {
        cancelarModalConsentimento();
      }
    }
  });

  function verificarModalConsentimento(tabId, callbackProsseguir) {
    let consentimentoSwing = null;
    let consentimentoAlocacao = null;
    try {
      consentimentoSwing = localStorage.getItem('caferadar_consent_swing');
      consentimentoAlocacao = localStorage.getItem('caferadar_consent_alocacao');
    } catch (e) {}

    if (tabId === 'swingtrade' && !consentimentoSwing) {
      const modalSwing = document.getElementById('modal-governanca-swing');
      const btnConcordo = document.getElementById('btn-concordo-swing');
      const btnCancelar = document.getElementById('btn-cancelar-swing');
      const backdrop = modalSwing ? modalSwing.querySelector('.modal-governanca-backdrop') : null;
      if (modalSwing && btnConcordo) {
        modalSwing.style.display = 'flex';
        btnConcordo.focus();
        btnConcordo.onclick = function() {
          try { localStorage.setItem('caferadar_consent_swing', 'true'); } catch (e) {}
          modalSwing.style.display = 'none';
          callbackProsseguir();
        };
        if (btnCancelar) btnCancelar.onclick = cancelarModalConsentimento;
        if (backdrop) backdrop.onclick = cancelarModalConsentimento;
        return false;
      }
    } else if (tabId === 'alocacao' && !consentimentoAlocacao) {
      const modalAlocacao = document.getElementById('modal-governanca-alocacao');
      const btnConcordoAloc = document.getElementById('btn-concordo-alocacao');
      const btnCancelarAloc = document.getElementById('btn-cancelar-alocacao');
      const backdropAloc = modalAlocacao ? modalAlocacao.querySelector('.modal-governanca-backdrop') : null;
      if (modalAlocacao && btnConcordoAloc) {
        modalAlocacao.style.display = 'flex';
        btnConcordoAloc.focus();
        btnConcordoAloc.onclick = function() {
          try { localStorage.setItem('caferadar_consent_alocacao', 'true'); } catch (e) {}
          modalAlocacao.style.display = 'none';
          callbackProsseguir();
        };
        if (btnCancelarAloc) btnCancelarAloc.onclick = cancelarModalConsentimento;
        if (backdropAloc) backdropAloc.onclick = cancelarModalConsentimento;
        return false;
      }
    }
    return true;
  }

  // Inicializacao inteligente e segura do Google AdSense
  function inicializarAnunciosAdSense(container) {
    try {
      if (typeof window.adsbygoogle === 'undefined') {
        window.adsbygoogle = [];
      }
      var escopo = container || document;
      var slots = escopo.querySelectorAll('ins.adsbygoogle:not([data-adsbygoogle-status]):not([data-ad-pushed])');
      slots.forEach(function (slot) {
        if (slot.offsetParent !== null) {
          try {
            slot.setAttribute('data-ad-pushed', 'true');
            (window.adsbygoogle = window.adsbygoogle || []).push({});
          } catch (e) {
            console.debug('AdSense slot push diferido:', e.message);
          }
        }
      });
    } catch (err) {
      console.debug('AdSense init error:', err.message);
    }
  }

  window.trocarTab = function (tabId) {
    if (!tabId) return;

    const idLimpo = tabId.replace(/^tab-/, '');

    // Verifica modal de consentimento informado antes de exibir Swing Trade ou Radar Longo Prazo
    if (!verificarModalConsentimento(idLimpo, function() { window.trocarTab(idLimpo); })) {
      return;
    }

    abaAtual = idLimpo;

    // Atualiza botões e atributos ARIA
    document.querySelectorAll('.btn-tab[data-tab]').forEach(function (btn) {
      const dt = btn.getAttribute('data-tab') || '';
      const ativa = (dt === idLimpo || dt === 'tab-' + idLimpo);
      btn.classList.toggle('ativa', ativa);
      btn.setAttribute('aria-selected', ativa ? 'true' : 'false');
      btn.setAttribute('tabindex', ativa ? '0' : '-1');
    });

    // Atualiza seções de conteúdo
    document.querySelectorAll('.conteudo-tab').forEach(function (sec) {
      sec.classList.remove('ativa');
    });

    const secAlvo = document.getElementById(idLimpo) || document.getElementById('tab-' + idLimpo);
    if (secAlvo) {
      secAlvo.classList.add('ativa');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      setTimeout(function () { inicializarAnunciosAdSense(secAlvo); }, 100);
    }

    // Atualiza hash sem saltos na página
    if (history.pushState && window.location.hash !== '#' + idLimpo) {
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
  let dadosSwingCache = null;
  let dadosRadarCache = null;

  function ehModoSemPregao(dados) {
    if (dados && dados.fim_de_semana === true) return true;
    try {
      const sp = obterAgoraSaoPaulo();
      return !ehDiaPregaoB3(sp.dtUtc);
    } catch (e) {
      return false;
    }
  }

  function extrairDataIso(valor) {
    if (typeof valor !== 'string') return '';
    const m = valor.trim().match(/^(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : '';
  }

  function formatarDdMmDeIso(iso) {
    const dt = extrairDataIso(iso);
    if (!dt) return '';
    return dt.slice(8, 10) + '/' + dt.slice(5, 7);
  }

  function edicaoEhDeHoje(ed, dadosRaiz, spHojeIso) {
    if (!ed || typeof ed !== 'object') return false;
    if (ed.disponivel === false) return false;
    if (ed.sem_captura_legitima === true) return false;
    const dtCap = extrairDataIso(ed.capturado_em);
    const dtEd = extrairDataIso(ed.data_referencia);
    const dtGeral = extrairDataIso(dadosRaiz && dadosRaiz.data_referencia);
    const dtEfetiva = dtCap || dtEd || dtGeral;
    return Boolean(dtEfetiva && dtEfetiva === spHojeIso);
  }

  function montarItensMercadoEdicao(ed) {
    const itens = [];
    if (!ed || !ed.mercado_geral || typeof ed.mercado_geral !== 'object') return itens;
    const mg = ed.mercado_geral;
    const blueChips = Array.isArray(ed.acoes_blue_chips) ? ed.acoes_blue_chips : [];

    if (mg.ibov && (mg.ibov.pontos || mg.ibov.valor)) {
      itens.push({ ticker: 'IBOV', preco: mg.ibov.pontos || mg.ibov.valor, variacao: mg.ibov.variacao, positivo: mg.ibov.positivo });
    }
    if (mg.dolar && mg.dolar.valor) {
      itens.push({ ticker: 'DÓLAR', preco: mg.dolar.valor, variacao: mg.dolar.variacao, positivo: mg.dolar.positivo });
    }
    if (mg.sp500 && (mg.sp500.valor || mg.sp500.pontos)) {
      itens.push({ ticker: 'S&P 500', preco: mg.sp500.valor || mg.sp500.pontos, variacao: mg.sp500.variacao, positivo: mg.sp500.positivo });
    }
    if (blueChips.length > 0) {
      blueChips.forEach(function (ac) {
        if (ac && ac.ticker && ac.preco) {
          itens.push({
            ticker: ac.ticker,
            preco: ac.preco,
            variacao: ac.variacao_dia || ac.variacao,
            positivo: ac.positivo
          });
        }
      });
    }
    if (mg.bitcoin && mg.bitcoin.valor) {
      itens.push({ ticker: 'BTC', preco: mg.bitcoin.valor, variacao: mg.bitcoin.variacao, positivo: mg.bitcoin.positivo });
    }
    if (mg.brent && mg.brent.valor) {
      itens.push({ ticker: 'BRENT', preco: mg.brent.valor, variacao: mg.brent.variacao, positivo: mg.brent.positivo });
    }
    return itens;
  }

  function renderizarPainelFimDeSemana() {
    const painel = document.getElementById('painel-fim-de-semana');
    if (!painel) return;

    const sp = obterAgoraSaoPaulo();
    const semPregao = ehModoSemPregao(dadosFechamentoCache);

    if (!semPregao) {
      painel.style.display = 'none';
      return;
    }

    painel.style.display = 'block';
    const badgeEl = document.getElementById('fds-badge-status');
    const tituloEl = document.getElementById('fds-titulo-principal');
    const subEl = document.getElementById('fds-subtitulo-principal');

    if (badgeEl) badgeEl.textContent = '☕ ESPECIAL DE FIM DE SEMANA & PLANEJAMENTO DA SEMANA';
    if (tituloEl) tituloEl.textContent = 'Mercado B3 Fechado: Central de Estudos & Radar para Segunda-feira';
    if (subEl) subEl.textContent = 'Aproveite a pausa do pregão para revisar o balanço consolidado da semana, acompanhar as ações monitoradas pelo scanner quantitativo (+5%) e planejar seus aportes com tranquilidade.';

    // Atualizar status do Bitcoin 24/7 na agenda (apenas se edição elegível de hoje)
    const elBtcStatus = document.getElementById('fds-btc-status');
    if (elBtcStatus) {
      let btcExibido = false;
      if (dadosFechamentoCache && dadosFechamentoCache.edicoes) {
        const eds = dadosFechamentoCache.edicoes;
        const candidatos = [eds.fechamento, eds.negocios, eds.almoco, eds.abertura];
        const edRef = candidatos.find(function (ed) {
          return edicaoEhDeHoje(ed, dadosFechamentoCache, sp.dataIso) &&
            ed.mercado_geral && ed.mercado_geral.bitcoin &&
            ed.mercado_geral.bitcoin.valor && ed.mercado_geral.bitcoin.valor !== 'Indisponível';
        });
        const btc = edRef && edRef.mercado_geral && edRef.mercado_geral.bitcoin;
        if (btc && btc.valor) {
          const seta = btc.positivo ? '▲' : (btc.positivo === false ? '▼' : '');
          const varStr = btc.variacao && btc.variacao !== '—' ? ` (${[seta, btc.variacao].filter(Boolean).join(' ')})` : '';
          elBtcStatus.textContent = `Bitcoin cotado a ${btc.valor}${varStr} em negociação contínua.`;
          btcExibido = true;
        }
      }
      if (!btcExibido) {
        elBtcStatus.textContent = 'Bitcoin operando continuamente no fim de semana.';
      }
    }

    // Atualizar Card 2: Ações no Radar Técnico (Swing Trade +5%)
    const elSwingConteudo = document.getElementById('fds-radar-swing-conteudo');
    if (elSwingConteudo && dadosSwingCache) {
      const r = dadosSwingCache.resumo_pregao_hoje || dadosSwingCache.resumo_pregão_hoje || {};
      const pos = Array.isArray(dadosSwingCache.posicoes_destaque) ? dadosSwingCache.posicoes_destaque : [];
      const destaquesRadar = pos.filter(function(p) {
        return p.categoria === 'OPORTUNIDADE' || p.categoria === 'OPORTUNIDADE_COM_RESSALVA' || p.categoria === 'OBSERVAR' || p.categoria === 'AGUARDAR' || p.categoria === 'ALVO_ATINGIDO';
      }).slice(0, 3);
      const listaExibir = destaquesRadar.length > 0 ? destaquesRadar : pos.slice(0, 3);

      let htmlSwing = `<div style="margin-bottom:8px;font-size:0.79rem;color:#94a3b8;">Resumo das 59 ações: <strong style="color:#4ade80;">${r.oportunidades || 0} sinais ativos</strong> · <strong style="color:#fbbf24;">${r.ressalvas || 0} em observação</strong> · <strong style="color:#38bdf8;">${r.aguardando || 0} aguardando gatilho</strong></div>`;
      listaExibir.forEach(function(item) {
        const corTag = (item.categoria === 'OPORTUNIDADE') ? '#4ade80' : ((item.categoria === 'OBSERVAR' || item.categoria === 'OPORTUNIDADE_COM_RESSALVA') ? '#fbbf24' : '#38bdf8');
        htmlSwing += `
          <div class="fds-mini-item">
            <div>
              <strong style="color:#ffffff;font-family:var(--fonte-mono);">${escaparHtml(item.ticker)}</strong>
              <span style="color:#94a3b8;font-size:0.75rem;margin-left:4px;">${escaparHtml(item.setup || '')}</span>
            </div>
            <span style="color:${corTag};font-weight:700;font-size:0.75rem;">${escaparHtml(item.status_badge || item.categoria)}</span>
          </div>
        `;
      });
      elSwingConteudo.innerHTML = htmlSwing;
    }

    // Atualizar Card 4: Resumo Alocação 2038
    const elResumoAloc = document.getElementById('fds-resumo-alocacao');
    if (elResumoAloc && dadosRadarCache && dadosRadarCache.allocation) {
      const al = dadosRadarCache.allocation;
      const ind = dadosRadarCache.indicators || {};
      const taxaIpca = (ind.tesouro_ipca2040 && ind.tesouro_ipca2040.last_buy_rate_percent) ? formatarNumero(ind.tesouro_ipca2040.last_buy_rate_percent, 2) + '% a.a.' : '6,55% a.a.';
      elResumoAloc.innerHTML = `
        <div style="margin-bottom:8px;font-size:0.8rem;color:#cbd5e1;">Taxa real do <strong>Tesouro IPCA+ 2040</strong> em <strong style="color:#38bdf8;">${escaparHtml(taxaIpca)}</strong> (acima da meta de 6,50% a.a.):</div>
        <div class="fds-mini-item"><span>🇧🇷 Tesouro IPCA+ 2040</span><strong style="color:#38bdf8;font-family:var(--fonte-mono);">${Number(al['Tesouro IPCA+ 2040'] ?? 60)}%</strong></div>
        <div class="fds-mini-item"><span>🌎 S&amp;P 500 (IVVB11)</span><strong style="color:#4ade80;font-family:var(--fonte-mono);">${Number(al['IVVB11'] ?? 30)}%</strong></div>
        <div class="fds-mini-item"><span>₿ Bitcoin (Cripto)</span><strong style="color:#fbbf24;font-family:var(--fonte-mono);">${Number(al['Bitcoin'] ?? 10)}%</strong></div>
      `;
    }
  }

  function renderizarFitaCotacoes(dados) {
    const trilho = document.getElementById('fita-cotacoes-trilho');
    const elRefFita = document.getElementById('fita-referencia');
    if (!trilho) return;

    const sp = obterAgoraSaoPaulo();
    const hojeIso = sp.dataIso;
    const edicoes = (dados && dados.edicoes) || {};
    const temMapaEdicoes = Boolean(dados && dados.edicoes && typeof dados.edicoes === 'object');

    // Ordem de preferência entre edições elegíveis de hoje: fechamento > negocios > almoco > abertura
    let candidatos = [];
    if (temMapaEdicoes) {
      candidatos = [edicoes.fechamento, edicoes.negocios, edicoes.almoco, edicoes.abertura];
    } else if (dados && typeof dados === 'object') {
      candidatos = [dados];
    }

    let refEd = null;
    let itens = [];
    for (let i = 0; i < candidatos.length; i++) {
      const cand = candidatos[i];
      if (!edicaoEhDeHoje(cand, dados, hojeIso)) continue;
      const itensCand = montarItensMercadoEdicao(cand);
      const temValorReal = itensCand.some(function (it) {
        return it.preco && it.preco !== 'Indisponível' && it.preco !== 'indisponível';
      });
      if (itensCand.length > 0 && temValorReal) {
        refEd = cand;
        itens = itensCand;
        break;
      }
    }

    if (!refEd || itens.length === 0) {
      if (elRefFita && !String(elRefFita.textContent || '').trim()) {
        elRefFita.textContent = '(última edição)';
      }
      return;
    }

    const htmlItens = itens.map(function (item) {
      const pos = item.positivo;
      const cls = pos === true ? 'positivo' : (pos === false ? 'negativo' : '');
      const seta = pos === true ? '▲' : (pos === false ? '▼' : '');
      return '<span class="fita-item">' +
        '<span class="fita-ticker">' + escaparHtml(item.ticker) + '</span> ' +
        '<span class="fita-preco">' + escaparHtml(item.preco || '') + '</span> ' +
        '<span class="fita-var ' + cls + '">' + seta + ' ' + escaparHtml(item.variacao || '') + '</span>' +
        '</span>';
    }).join('');

    const htmlDuplicado = itens.map(function (item) {
      const pos = item.positivo;
      const cls = pos === true ? 'positivo' : (pos === false ? 'negativo' : '');
      const seta = pos === true ? '▲' : (pos === false ? '▼' : '');
      return '<span class="fita-item" aria-hidden="true">' +
        '<span class="fita-ticker">' + escaparHtml(item.ticker) + '</span> ' +
        '<span class="fita-preco">' + escaparHtml(item.preco || '') + '</span> ' +
        '<span class="fita-var ' + cls + '">' + seta + ' ' + escaparHtml(item.variacao || '') + '</span>' +
        '</span>';
    }).join('');

    trilho.innerHTML = htmlItens + htmlDuplicado;

    if (elRefFita) {
      const dtTxt = formatarDdMmDeIso(refEd.capturado_em) ||
        formatarDdMmDeIso(refEd.data_referencia) ||
        formatarDdMmDeIso(dados && dados.data_referencia) ||
        ((dados && dados.data_formatada) ? String(dados.data_formatada).slice(0, 5) : '');
      const hrTxt = (refEd && (refEd.horario_exibicao || refEd.horario)) || ((dados && dados.atualizado_as) || '');
      if (dtTxt || hrTxt) {
        elRefFita.textContent = '(' + [dtTxt, hrTxt].filter(Boolean).join(' ') + ')';
      } else {
        elRefFita.textContent = '(última edição)';
      }
    }
  }

  async function carregarFechamentoDiario() {
    try {
      const resp = await fetch('data/fechamento.json?_t=' + Date.now(), { cache: 'no-store' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const dados = await resp.json();
      dadosFechamentoCache = dados;
      renderizarFitaCotacoes(dados);
      configurarBotoesEdicao(dados);
      renderizarPainelFimDeSemana();
      const semPregao = ehModoSemPregao(dados);
      const edicaoInicial = semPregao ? 'fechamento' : (dados.edicao_padrao || 'fechamento');
      exibirEdicao(edicaoInicial);
    } catch (err) {
      console.warn('Usando dados de fallback para Fechamento Diário:', err.message);
      const fallback = obterFechamentoFallback();
      dadosFechamentoCache = fallback;
      renderizarFitaCotacoes(fallback);
      configurarBotoesEdicao(fallback);
      renderizarPainelFimDeSemana();
      exibirEdicao('fechamento');
    }
  }

  function configurarBotoesEdicao(dados) {
    const botoes = document.querySelectorAll('.btn-edicao');
    const semPregao = ehModoSemPregao(dados);
    const rotuloEl = document.getElementById('rotulo-seletor-edicoes');
    if (rotuloEl) {
      rotuloEl.textContent = semPregao ? 'Especial de Fim de Semana:' : 'Edições de Hoje:';
    }

    const mapaFds = {
      abertura: { icone: '📅', nome: 'Mapa da Semana', hora: 'Especial' },
      negocios: { icone: '🎯', nome: 'Radar de Segunda', hora: 'Estudo' },
      fechamento: { icone: '🏁', nome: 'Balanço da Semana', hora: 'Consolidado' }
    };
    const mapaUtil = {
      abertura: { icone: '🌅', nome: 'Café Matinal', hora: '08h00' },
      negocios: { icone: '🔔', nome: 'Abertura B3', hora: '10h30' },
      fechamento: { icone: '🏁', nome: 'Fechamento', hora: '18h15' }
    };

    botoes.forEach(function (btn) {
      const idEdicao = btn.getAttribute('data-edicao');
      const ed = dados.edicoes && dados.edicoes[idEdicao];
      const iconeEl = btn.querySelector('.edicao-icone');
      const nomeEl = btn.querySelector('.edicao-nome');
      const horaEl = btn.querySelector('.edicao-hora');
      const info = semPregao ? mapaFds[idEdicao] : mapaUtil[idEdicao];

      if (info) {
        if (iconeEl) iconeEl.textContent = info.icone;
        if (nomeEl) nomeEl.textContent = (ed && ed.nome && semPregao) ? ed.nome : info.nome;
      }

      if (!semPregao && ed && ed.disponivel === false) {
        btn.classList.add('edicao-pendente');
        if (horaEl) {
          const semCapBtn = ed.status_publicacao === 'Sem captura no horário' || ed.sem_captura_legitima === true;
          horaEl.textContent = semCapBtn ? '— Não publicada' : ('⏳ ' + (ed.horario || (info ? info.hora : '')));
        }
      } else {
        btn.classList.remove('edicao-pendente');
        if (horaEl) {
          horaEl.textContent = semPregao ? (info ? info.hora : 'Disponível') : ((ed && ed.horario) || (info ? info.hora : ''));
        }
      }

      btn.onclick = function (e) {
        e.preventDefault();
        exibirEdicao(idEdicao);
      };
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

    const edMap = dadosFechamentoCache.edicoes || {};
    let dadosEdicao = null;
    if (edMap[idEdicao]) {
      dadosEdicao = edMap[idEdicao];
    } else if (idEdicao === 'negocios' && edMap.almoco) {
      dadosEdicao = edMap.almoco;
    } else if (!dadosFechamentoCache.edicoes && dadosFechamentoCache.mercado_geral) {
      dadosEdicao = dadosFechamentoCache;
    }

    const boxPublicada = document.getElementById('conteudo-edicao-publicada');
    const boxAguardando = document.getElementById('conteudo-edicao-aguardando');
    const semPregao = ehModoSemPregao(dadosFechamentoCache);

    const NOME_FALLBACK = { abertura: 'Café Matinal', negocios: 'Abertura B3', almoco: 'Abertura B3', fechamento: 'Fechamento' };
    const HORARIO_FALLBACK = { abertura: '08h00', negocios: '10h30', almoco: '10h30', fechamento: '18h15' };
    const JANELA_FIM_MIN = { abertura: 9 * 60 + 45, negocios: 12 * 60, almoco: 12 * 60, fechamento: 23 * 60 + 59 };

    const edicaoAusenteOuIndisp = (!dadosEdicao) || (!semPregao && dadosEdicao.disponivel === false);

    // Se a edição não existe (JSON vazio) ou ainda não está disponível no pregão útil
    if (edicaoAusenteOuIndisp) {
      if (boxPublicada) boxPublicada.style.display = 'none';
      if (boxAguardando) {
        boxAguardando.style.display = 'block';

        const sp = obterAgoraSaoPaulo();
        const dataRefArquivo = (dadosEdicao && extrairDataIso(dadosEdicao.data_referencia)) ||
          extrairDataIso(dadosFechamentoCache.data_referencia) || '';
        const dataFmtArquivo = (dadosEdicao && dadosEdicao.data_formatada) ||
          dadosFechamentoCache.data_formatada || formatarData(dataRefArquivo) || '';
        const ehMesmoDia = (!dataRefArquivo || dataRefArquivo === sp.dataIso);
        const ehDiaPassado = Boolean(dataRefArquivo && dataRefArquivo < sp.dataIso);

        const nomeEdSeguro = (dadosEdicao && dadosEdicao.nome) || NOME_FALLBACK[idEdicao] || 'Pregão B3';
        const horarioSeguro = (dadosEdicao && dadosEdicao.horario) || HORARIO_FALLBACK[idEdicao] || '18h15';

        let tempoPrevistoMin = 0;
        const mHorario = String(horarioSeguro).match(/^(\d{2})h(\d{2})/);
        if (mHorario) {
          tempoPrevistoMin = parseInt(mHorario[1], 10) * 60 + parseInt(mHorario[2], 10);
        }
        const tempoFimJanela = JANELA_FIM_MIN[idEdicao] || 0;

        const jaPassouNoMesmoDia = ehMesmoDia && tempoPrevistoMin > 0 && sp.totalMin >= tempoPrevistoMin;
        const passouJanelaNoDia = ehMesmoDia && tempoFimJanela > 0 && sp.totalMin > tempoFimJanela;
        const statusSemCaptura = Boolean(dadosEdicao && (
          dadosEdicao.status_publicacao === 'Sem captura no horário' ||
          dadosEdicao.sem_captura_legitima === true
        ));

        // Descobrir edição realmente disponível no cache para oferecer botão de retorno preciso
        let edVoltarKey = null;
        let edVoltarLabel = '';
        const ordemRetorno = ['fechamento', 'negocios', 'abertura'];
        for (let r = 0; r < ordemRetorno.length; r++) {
          const rk = ordemRetorno[r];
          if (rk === idEdicao) continue;
          const cand = edMap[rk];
          if (cand && cand.disponivel === true) {
            edVoltarKey = rk;
            edVoltarLabel = `Edição de ${cand.nome || NOME_FALLBACK[rk]} (${cand.horario || HORARIO_FALLBACK[rk]})`;
            break;
          }
        }

        let tituloAguardando = '';
        let textoAguardando = '';
        let badgeAguardando = '';

        if (!dadosEdicao && !dataRefArquivo) {
          tituloAguardando = `Edição não publicada hoje (${escaparHtml(nomeEdSeguro)})`;
          textoAguardando = 'Nenhuma edição disponível foi publicada até o momento. Consulte o acervo histórico de fechamentos ou os indicadores de longo prazo.';
          badgeAguardando = '● Sem edições publicadas no momento';
        } else if (ehDiaPassado) {
          tituloAguardando = `Edição de ${escaparHtml(nomeEdSeguro)} (${escaparHtml(dataFmtArquivo)}) Não Publicada`;
          textoAguardando = `A consolidação desta edição de ${escaparHtml(dataFmtArquivo)} não foi registrada no ciclo automático. Você pode consultar outra edição disponível ou o acervo completo.`;
          badgeAguardando = `● Edição de ${escaparHtml(dataFmtArquivo)} indisponível`;
        } else if (statusSemCaptura || (jaPassouNoMesmoDia && passouJanelaNoDia)) {
          tituloAguardando = `Edição não publicada hoje — ${escaparHtml(nomeEdSeguro)}`;
          textoAguardando = `O horário previsto para esta edição (${escaparHtml(horarioSeguro)}) encerrou-se hoje sem captura publicada. Consulte outra edição disponível ou acesse o acervo.`;
          badgeAguardando = `● Edição não publicada hoje (${escaparHtml(horarioSeguro)})`;
        } else if (jaPassouNoMesmoDia) {
          tituloAguardando = `Edição de ${escaparHtml(nomeEdSeguro)} em Consolidação`;
          textoAguardando = `O horário nominal (${escaparHtml(horarioSeguro)}) foi atingido e a captura encontra-se dentro da janela de consolidação automática.`;
          badgeAguardando = `● Horário nominal: ${escaparHtml(horarioSeguro)}`;
        } else {
          tituloAguardando = `Edição de ${escaparHtml(nomeEdSeguro)} Prevista para as ${escaparHtml(horarioSeguro)}`;
          textoAguardando = `A síntese, cotações consolidadas e destaques do mercado para esta edição têm publicação programada para as <strong>${escaparHtml(horarioSeguro)}</strong> (horário de Brasília).`;
          badgeAguardando = `● Publicação programada: ${escaparHtml(horarioSeguro)}`;
        }

        const btnAcaoHtml = edVoltarKey
          ? `<button type="button" id="btn-voltar-abertura" class="btn-tab ativa" style="padding: 10px 22px; border-radius: var(--raio-md); cursor: pointer; border: 1px solid var(--borda);">← Acessar ${escaparHtml(edVoltarLabel)}</button>`
          : `<a href="edicoes/" class="btn-tab ativa" style="display:inline-block; padding: 10px 22px; border-radius: var(--raio-md); text-decoration:none; border: 1px solid var(--borda);">📚 Acessar Acervo Histórico →</a>`;

        boxAguardando.innerHTML = `
          <div class="card-bloco-noticia" style="text-align:center; padding: 56px 24px; margin-top: 16px;">
            <div style="font-size: 3.2rem; margin-bottom: 14px;" aria-hidden="true">⏳</div>
            <h3 style="font-size: 1.45rem; color: var(--primaria); font-weight: 800; margin-bottom: 10px;">
              ${tituloAguardando}
            </h3>
            <p style="font-size: 1rem; color: var(--texto-secundario); max-width: 540px; margin: 0 auto 18px; line-height: 1.6;">
              ${textoAguardando}
            </p>
            <div style="display:inline-block; background: var(--destaque-suave); color: var(--destaque); padding: 6px 16px; border-radius: 9999px; font-weight: 700; font-size: 0.88rem; margin-bottom: 24px;">
              ${badgeAguardando}
            </div>
            <div>
              ${btnAcaoHtml}
            </div>
          </div>
        `;
        const btnVoltar = document.getElementById('btn-voltar-abertura');
        if (btnVoltar && edVoltarKey) {
          btnVoltar.addEventListener('click', function () {
            exibirEdicao(edVoltarKey);
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

    const dataFinal = dataGeral || dados.data_formatada || '—';
    const elDataBadge = document.getElementById('badge-data-fechamento');
    if (elDataBadge) elDataBadge.textContent = dataFinal;

    const elAtualizacao = document.getElementById('fechamento-atualizacao');
    if (elAtualizacao) {
      const hora = dados.horario || dados.atualizado_as || '18h15';
      const nomeEd = dados.nome ? `(${dados.nome})` : '';
      elAtualizacao.textContent = `Edição de ${dataFinal} às ${hora} ${nomeEd}`;
    }

    const elTitulo = document.getElementById('fechamento-titulo');
    if (elTitulo && dados.titulo) elTitulo.textContent = dados.titulo;

    const elSubtitulo = document.getElementById('fechamento-subtitulo');
    if (elSubtitulo && dados.subtitulo) elSubtitulo.textContent = dados.subtitulo;

    const elHeroImg = document.getElementById('fechamento-hero-img');
    if (elHeroImg && dadosFechamentoCache) {
      const dataRef = dadosFechamentoCache.data_referencia || '2026-11-09';
      let cardTipo = 'fechamento';
      const idOuNome = (dados.id || dados.nome || '').toLowerCase();
      if (idOuNome.includes('matinal') || idOuNome.includes('mapa') || idOuNome === 'abertura') {
        cardTipo = 'abertura';
      } else if (idOuNome.includes('negocios') || idOuNome.includes('abertura b3') || idOuNome.includes('almoco')) {
        cardTipo = 'negocios';
      }
      elHeroImg.src = `marketing_output/${dataRef}_${cardTipo}_x.png`;
      elHeroImg.alt = `${dados.titulo || 'Síntese do Pregão B3'} — CafeRadar`;
    }

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
      dadosSwingCache = dados;
      renderizarSwingTrade(dados);
      renderizarPainelFimDeSemana();
    } catch (err) {
      console.warn('Usando dados de fallback para Swing Trade:', err.message);
      const fb = obterSwingFallback();
      dadosSwingCache = fb;
      renderizarSwingTrade(fb);
      renderizarPainelFimDeSemana();
    }
  }

  /**
   * Determina a defasagem em pregões B3 e status de frescor dinamicamente a partir de data_referencia.
   * Considera o fuso horário de São Paulo (America/Sao_Paulo).
   * Fallback explícito: Cálculo padrão por dias úteis B3 (segunda a sexta, excluindo fins de semana).
   */
  function calcularFrescorDinamico(dataRefStr) {
    if (!dataRefStr || !/^\d{4}-\d{2}-\d{2}$/.test(dataRefStr)) {
      return { status: 'DESATUALIZADO', defasagem: 999, fallback: 'data_invalida' };
    }

    try {
      // Obter data atual no fuso de São Paulo
      const agora = new Date();
      const spFormatter = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'America/Sao_Paulo',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      });
      const dataSpStr = spFormatter.format(agora); // YYYY-MM-DD
      const partesRef = dataRefStr.split('-').map(Number);
      const partesHoje = dataSpStr.split('-').map(Number);

      const dRef = new Date(Date.UTC(partesRef[0], partesRef[1] - 1, partesRef[2]));
      const dHoje = new Date(Date.UTC(partesHoje[0], partesHoje[1] - 1, partesHoje[2]));

      if (dRef > dHoje) {
        return { status: 'ATUALIZADO', defasagem: 0, fallback: 'data_futura' };
      }

      // Contagem de pregões B3 (exclui sábados, domingos e feriados oficiais da B3)
      let contagem = 0;
      let cur = new Date(dRef.getTime() + 86400000);

      while (cur <= dHoje) {
        if (ehDiaPregaoB3(cur)) {
          contagem++;
        }
        cur = new Date(cur.getTime() + 86400000);
      }

      // Regime B3 regular: sessão atual (0) ou sessão imediatamente anterior (1) é ATUALIZADO
      const status = contagem <= 1 ? 'ATUALIZADO' : 'DESATUALIZADO';
      return { status: status, defasagem: contagem, fallback: 'calendario_b3' };
    } catch (e) {
      console.warn('Falha no cálculo dinâmico de frescor, usando dados brutos:', e);
      return { status: 'DESATUALIZADO', defasagem: 999, fallback: 'erro' };
    }
  }

  function renderizarSwingTrade(dados) {
    if (!dados) return;

    // 0. Frescor dos dados e execução do scanner
    const elFrescorTexto = document.getElementById('st-frescor-texto');
    const elBadgeFrescor = document.getElementById('st-badge-frescor');
    const containerFrescor = document.getElementById('st-frescor-container');

    if (containerFrescor && elFrescorTexto && elBadgeFrescor) {
      const dataRef = dados.data_referencia;
      const dataExec = dados.data_execucao_scanner || dados.atualizado_em;
      // 0.1 Cálculo de frescor dinâmico no frontend (Fuso de São Paulo)
      const dinamico = calcularFrescorDinamico(dataRef);
      // O frontend não confia exclusivamente no JSON: se a defasagem real superar 1 pregão, força DESATUALIZADO
      const statusFrescor = (dinamico.defasagem > 1) ? 'DESATUALIZADO' : (dados.status_frescor || dinamico.status);
      const defasagem = dinamico.defasagem !== null ? dinamico.defasagem : (typeof dados.dias_uteis_defasagem === 'number' ? dados.dias_uteis_defasagem : null);
      const avisoFrescorExtra = dados.aviso_frescor ? ` (${escaparHtml(dados.aviso_frescor)})` : '';

      // Formatar data_referencia (YYYY-MM-DD -> DD/MM)
      let dataRefFmt = '—';
      if (dataRef && /^\d{4}-\d{2}-\d{2}$/.test(dataRef)) {
        const p = dataRef.split('-');
        dataRefFmt = `${p[2]}/${p[1]}`;
      } else if (dataRef && dataRef !== '—') {
        dataRefFmt = String(dataRef);
      }

      // Formatar data_execucao_scanner (ex: "04/11/2026 às 10h18" -> "04/11 às 10h18")
      let dataExecFmt = '—';
      if (dataExec && dataExec !== '—') {
        const mExec = String(dataExec).match(/^(\d{2})\/(\d{2})\/\d{4}\s+às\s+(\d{2}h\d{2})/);
        if (mExec) {
          dataExecFmt = `${mExec[1]}/${mExec[2]} às ${mExec[3]}`;
        } else {
          dataExecFmt = String(dataExec);
        }
      }

      if (statusFrescor === 'ATUALIZADO') {
        containerFrescor.classList.remove('alerta-desatualizado');
        containerFrescor.style.borderLeft = '';
        elBadgeFrescor.className = 'badge-frescor atualizado';
        elBadgeFrescor.textContent = 'Scanner Atualizado';
        elFrescorTexto.innerHTML = `<strong>Dados de ${escaparHtml(dataRefFmt)}</strong> — scanner executado em ${escaparHtml(dataExecFmt)}`;
      } else {
        // Exibir faixa vermelha destacada quando defasagem superar um pregão ou estiver desatualizado
        containerFrescor.classList.add('alerta-desatualizado');
        containerFrescor.style.borderLeft = '6px solid var(--baixa, #dc2626)';
        containerFrescor.style.background = 'rgba(239, 68, 68, 0.08)';
        elBadgeFrescor.className = 'badge-frescor desatualizado';
        elBadgeFrescor.textContent = (defasagem !== null && defasagem < 999)
          ? `Desatualizado (${defasagem} pregões)`
          : 'Dados Desatualizados';
        elFrescorTexto.innerHTML = `<span style="color:var(--baixa, #dc2626); font-weight:800;">🚨 DADOS DEFASADOS (${defasagem !== null ? defasagem + ' pregões' : ''}):</span> Dados de <strong>${escaparHtml(dataRefFmt)}</strong> — scanner executado em ${escaparHtml(dataExecFmt)}${avisoFrescorExtra}. O mercado mudou desde esta leitura; opere com cautela.`;
      }
    }

    // 1. Painel de Métricas do Motor
    const est = dados.estrategia || {};
    const elUni = document.getElementById('st-universo');
    if (elUni && est.universo_total) elUni.textContent = `${est.universo_total} Ações`;

    const elAlvo = document.getElementById('st-alvo');
    if (elAlvo && est.alvo_padrao_percentual) elAlvo.textContent = `+${est.alvo_padrao_percentual.toFixed(2)}%`;

    const elAssert = document.getElementById('st-assertividade');
    if (elAssert) {
      const venc = est.operacoes_vencedoras ?? 154;
      const abertas = est.operacoes_em_aberto ?? 19;
      const vermelho = est.operacoes_abertas_vermelho ?? 18;
      elAssert.textContent = `${venc} encerradas no alvo · ${abertas} em aberto (${vermelho} no vermelho)`;
    }

    const elAbertasDetalhe = document.getElementById('st-abertas-detalhe');
    if (elAbertasDetalhe) {
      elAbertasDetalhe.textContent = est.nota_metodologica || 'Sem stop loss, toda operação encerrada fecha no alvo por construção; o risco está nas posições em aberto. Backtest auditado, não é histórico de operações reais.';
    }

    const elTempo = document.getElementById('st-tempo');
    if (elTempo && est.tempo_medio_posicao) elTempo.textContent = est.tempo_medio_posicao;

    // 2. Termômetro do Scanner Hoje
    const containerTermo = document.getElementById('st-termometro');
    const resumoPregao = dados.resumo_pregao_hoje || dados.resumo_pregão_hoje;
    if (containerTermo && resumoPregao) {
      const r = resumoPregao;
      containerTermo.innerHTML = `
        <div class="item-termometro verde">
          <div>
            <div class="termo-nome">Sinais Técnicos Ativos</div>
            <span style="font-size:0.75rem;color:var(--alta);font-weight:600;">Filtro técnico preenchido</span>
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
            <span style="font-size:0.75rem;color:var(--neutro);font-weight:600;">Filtro restritivo de tendência</span>
          </div>
          <div class="termo-contagem" style="color:var(--neutro);">${r.desfavoravel || 0}</div>
        </div>
      `;
    }

    // 3. Tabela de Monitor de Oportunidades & Posições
    const MAPA_EMPRESAS_B3 = {
      'SAUD3': 'Mater Dei ON',
      'LEVE3': 'Mahle Metal Leve ON',
      'MBRF3': 'Marfrig / BRF ON',
      'POMO3': 'Marcopolo ON',
      'POMO4': 'Marcopolo PN',
      'BBDC3': 'Bradesco ON',
      'ITUB3': 'Itaú Unibanco ON',
      'ALOS3': 'Allos ON',
      'ISAE4': 'ISA Energia PN',
      'BRAP4': 'Bradespar PN',
      'RECV3': 'PetroRecôncavo ON',
      'BRSR6': 'Banrisul PNB',
      'JHSF3': 'JHSF ON',
      'BMOB3': 'Bemobi ON',
      'MDNE3': 'Moura Dubeux ON',
      'BMGB4': 'Banco BMG PN',
      'PGMN3': 'Pague Menos ON',
      'RANI3': 'Irani ON',
      'LAVV3': 'Lavvi ON',
      'BRBI11': 'BR Partners Unit',
      'EVEN3': 'Even ON'
    };
    const MAPA_SETUPS = {
      'TOQUE_SMA21': 'Toque na Média 21 (SMA21)',
      'REVERSAO_RSI': 'Reversão IFR (Sobrevenda)',
      'PULLBACK_SMA50': 'Pullback na Média 50 (SMA50)',
      'ROMPIMENTO_ CURTO': 'Rompimento de Curto Prazo',
      'NENHUM': 'Monitorando Média'
    };

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
        } else if (pos.categoria === 'OPORTUNIDADE_COM_RESSALVA' || pos.categoria === 'OBSERVAR') {
          badgeClasse = 'ressalva';
        } else if (pos.categoria === 'DESFAVORAVEL') {
          badgeClasse = 'desfavoravel';
        }

        const varAtualStr = String(pos.variacao_atual ?? '—');
        const corVar = varAtualStr.includes('-') ? 'var(--baixa)' : (varAtualStr === '—' ? 'inherit' : 'var(--alta)');
        const nomeEmpresa = (pos.empresa && pos.empresa !== pos.ticker) ? pos.empresa : (MAPA_EMPRESAS_B3[pos.ticker] || pos.empresa || pos.ticker);
        const nomeSetup = MAPA_SETUPS[pos.setup] || pos.setup || '—';

        tr.innerHTML = `
          <td>
            <span class="ticker-tag">${escaparHtml(pos.ticker)}</span>
            <span class="sub-empresa">${escaparHtml(nomeEmpresa)}</span>
          </td>
          <td style="font-size:0.85rem;">${escaparHtml(nomeSetup)}</td>
          <td class="cel-num">${escaparHtml(pos.preco_entrada)}</td>
          <td class="cel-num" style="color:var(--destaque);font-weight:700;">${escaparHtml(pos.alvo_saida)}</td>
          <td class="cel-num" style="color:${corVar};font-weight:700;">${escaparHtml(varAtualStr)}</td>
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
      dadosRadarCache = dados;
      renderizarRadar(dados, false);
      renderizarPainelFimDeSemana();
    } catch (err) {
      console.warn('Usando dados de fallback para Radar Longo Prazo:', err.message);
      const fb = obterRadarFallback();
      dadosRadarCache = fb;
      renderizarRadar(fb, true);
      renderizarPainelFimDeSemana();
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
    const elTxtMotor = document.getElementById('texto-status-motor');

    const dataRef = dados.reference_date || (dados.generated_at ? dados.generated_at.split('T')[0] : '—');
    if (elData) elData.textContent = formatarData(dataRef);
    if (elEstado) elEstado.textContent = dados.status || 'CONCLUÍDO';
    if (elTxtMotor && dataRef && dataRef !== '—') {
      elTxtMotor.textContent = 'Motor Quant (' + formatarData(dataRef).slice(0, 5) + ')';
    }

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

  function atualizarCardsPapelAtivos(alocacao) {
    if (!alocacao) return;
    const tatico = Number(alocacao['Caixa tático'] ?? alocacao['Caixa tatico'] ?? 0);
    const residual = Number(alocacao['Caixa residual'] ?? 0);
    const totalCaixa = Number(alocacao['Caixa'] ?? (tatico + residual));
    const mapaIds = {
      'card-perc-ipca': alocacao['Tesouro IPCA+ 2040'],
      'card-perc-ivvb': alocacao['IVVB11'],
      'card-perc-bova': alocacao['BOVA11'],
      'card-perc-btc': alocacao['Bitcoin'],
      'card-perc-caixa': totalCaixa
    };
    Object.keys(mapaIds).forEach(function (id) {
      const el = document.getElementById(id);
      const val = mapaIds[id];
      if (el && val !== null && val !== undefined) {
        el.textContent = `(${Number(val)}%)`;
      }
    });
  }

  function renderizarAlocacao(alocacao, elegibilidade, bloqueado) {
    const containerLista = document.getElementById('lista-alocacao');
    const containerGrafico = document.getElementById('grafico-pizza');

    if (!containerLista) return;
    containerLista.innerHTML = '';

    if (bloqueado || !alocacao) {
      containerLista.innerHTML = '<div class="aviso-execucao" style="background:#fee2e2;color:#991b1b;"><strong>ALOCAÇÃO BLOQUEADA PELO MOTOR:</strong> O motor suspendeu preventivamente o modelo de alocação por inconsistência nos dados de mercado.</div>';
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
    atualizarCardsPapelAtivos(alocacao);
  }

  function renderizarGraficoPizza(itens, container) {
    let acumulado = 0;
    const fatias = [];
    const itensValidos = itens.filter(i => Number(i.perc) > 0);
    const resumoAria = itens
      .map(i => `${i.nome}: ${i.perc !== null && i.perc !== undefined ? i.perc + '%' : '—'}`)
      .join(', ');

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
      <svg viewBox="0 0 100 100" class="grafico-pizza" role="img" aria-label="${escaparHtml('Gráfico de alocação teórica: ' + resumoAria)}" style="border-radius:50%; width:160px; height:160px;">
        <title>${escaparHtml('Alocação teórica: ' + resumoAria)}</title>
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
      data_referencia: '—',
      data_execucao_scanner: '—',
      status_frescor: 'DESATUALIZADO',
      dias_uteis_defasagem: 999,
      estrategia: {
        operacoes_vencedoras: 154,
        operacoes_totais_1ano: 173,
        operacoes_em_aberto: 19,
        operacoes_abertas_vermelho: 18,
        universo_total: 59,
        alvo_padrao_percentual: 5.0,
        tempo_medio_posicao: '11 pregões (mediana)'
      },
      resumo_pregão_hoje: { oportunidades: 1, ressalvas: 1, aguardando: 14, desfavoravel: 43 },
      posicoes_destaque: [
        { ticker: 'WEGE3', empresa: 'WEG S.A.', setup: 'Força Relativa', preco_entrada: 'R$ 48,35', alvo_saida: 'R$ 50,77 (+5%)', variacao_atual: '+1,67%', categoria: 'OPORTUNIDADE', status_badge: 'Em Andamento' },
        { ticker: 'BBSE3', empresa: 'BB Seguridade', setup: 'Reversão Suporte', preco_entrada: 'R$ 34,20', alvo_saida: 'R$ 35,91 (+5%)', variacao_atual: '+5,00%', categoria: 'ALVO_ATINGIDO', status_badge: 'Alvo Batido' }
      ],
      principais_regras_simples: [
        { titulo: '1. Universo de Liquidez Restrito', descricao: 'O algoritmo monitora as 59 empresas com maior liquidez e representatividade na B3.' },
        { titulo: '2. Parâmetro Matemático de Alvo (+5%)', descricao: 'Nos modelos de backtest, a posição teórica encerra-se automaticamente ao atingir +5% sobre o preço de ativação do filtro.' },
        { titulo: '3. Filtro Restritivo de Tendência', descricao: 'Ativos em tendência de baixa sem confirmação estatística de reversão à média são classificados como Desfavorável.' }
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

  // =========================================================================
  // CALCULADORA DE RENDA FIXA INTERATIVA (SIMULADOR EDUCATIVO)
  // =========================================================================

  function inicializarCalculadoraRendaFixa() {
    const inputValor = document.getElementById('calc-valor');
    if (!inputValor) return;

    let mesesSelecionados = 12;

    function calcular() {
      const valor = parseFloat(inputValor.value) || 0;
      if (valor <= 0) return;

      // Taxas de referência do simulador (base nov/2026)
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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializar);
  } else {
    inicializar();
  }

})();
