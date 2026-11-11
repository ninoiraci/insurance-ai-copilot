# Sicurezza, privacy e limiti

*Traduzione italiana di [`docs/SECURITY_AND_LIMITATIONS.md`](../SECURITY_AND_LIMITATIONS.md).*

**Questo è un proof of concept. Non è software di produzione, e questo documento
esiste perché nessuno lo scambi per tale.**

In questo repository non viene fatta da nessuna parte alcuna dichiarazione di
conformità al GDPR. Il sistema elabora solo dati inventati e non ha mai trattato un
record cliente reale.

---

## 1. I dati in questo repository

Tutto è sintetico:

| Dato | Origine |
|---|---|
| 20 clienti | Nomi inventati, indirizzi `@example.invalid`, numeri di telefono generati |
| 39 polizze | Numeri generati, date scelte per far scattare le regole di business |
| 42 conversazioni, 102 messaggi | Scritte per questo progetto |
| 10 manuali di procedura | Scritti per questo progetto; realistici nella forma, non giuridicamente accurati |
| 60 casi di valutazione | Scritti per questo progetto |

`example.invalid` è riservato dalla RFC 2606 e non può mai instradare posta.
Nessuna persona, polizza, veicolo, sinistro o azienda reale è rappresentata, e non
è stato usato materiale proprietario di alcuna organizzazione.

I documenti di procedura fanno riferimento a concetti assicurativi spagnoli (il
termine di sette giorni per la denuncia di sinistro, il mese di opposizione al
rinnovo, la sospensione della copertura un mese dopo un premio non pagato). Sono
plausibili e usati in modo coerente, ma sono **illustrativi, non consulenza
legale**, e un'implementazione reale sostituirebbe tutti e dieci i documenti con le
procedure riviste del broker stesso.

---

## 2. Cosa **è** implementato

### Gestione dell'input
- Validazione Pydantic su ogni corpo di richiesta; campi sconosciuti rifiutati
  (`extra="forbid"`).
- Validazione degli enum sui parametri di query — un filtro non valido restituisce
  422, non un 500.
- Lunghezza del messaggio limitata a 8 000 caratteri prima di ogni chiamata API.
- Caratteri di controllo rimossi durante la normalizzazione.
- Query parametrizzate SQLAlchemy ovunque; l'unica istruzione SQL grezza (la
  ricerca pgvector) usa parametri legati.
- Un `X-Request-ID` in arrivo è controllato dall'attaccante, quindi viene validato
  contro un alfabeto e una lunghezza rigorosi prima di essere memorizzato,
  registrato o restituito; qualsiasi altra cosa viene sostituita con un id generato.

### Controlli specifici per l'AI
- **Validazione dello schema** su ogni output del modello. Un enum non valido non
  può raggiungere il database.
- **Ritentativi limitati** con l'errore concreto reimmesso, poi un fallback sicuro.
- **Euristiche anti prompt injection** — 13 pattern, inglese e spagnolo,
  insensibili agli accenti. Una corrispondenza salta il recupero, forza
  l'escalation alla compliance e scrive una voce di audit.
- **Difesa strutturale dalle injection** — il testo del cliente è sempre delimitato
  ed etichettato come non fidato, e **nessun percorso di codice può leggere i dati
  di un altro cliente**: il costruttore di contesto riceve un solo oggetto cliente.
- **Ancoraggio** — i fatti procedurali devono provenire dai chunk recuperati, e le
  citazioni sono verificate lato server contro ciò che è stato effettivamente
  recuperato.
- **Rifiuto esplicito** quando il recupero non restituisce nulla.
- **Human-in-the-loop** su ogni intento ad alto rischio, caso a bassa confidenza e
  bozza non ancorata.
- **Nessuna azione esterna automatica.** L'invio è simulato; l'audit trail registra
  `delivery: SIMULATED_ONLY`.

### Ingegneria orientata alla privacy
- I segreti vengono dall'ambiente; `.env` è in gitignore, `.env.example` non
  contiene valori reali.
- **I metadati di audit non contengono mai corpi di messaggi o bozze di risposta** —
  `_sanitise()` li rimuove per chiave.
- I corpi dei messaggi non vengono registrati; `LOG_MESSAGE_BODIES` è `false` per
  default.
- Un helper `redact()` maschera email, telefoni, IBAN e targhe per la rara riga di
  log che ha bisogno di un estratto.
- Le credenziali del database sono rimosse dalla riga di log di avvio.
- Gli errori restituiscono un messaggio generico; SQL e stack trace non
  raggiungono mai il client.
- I container girano con un utente non-root.
- Il prompt vieta di richiedere numeri di carta o credenziali bancarie,
  rispecchiando il documento di procedura interna.

---

## 3. Cosa **NON** è implementato

Questa è la sezione importante.

### Autenticazione e autorizzazione — del tutto assenti
- **Nessun login.** Ogni endpoint API è aperto a chiunque possa raggiungere la
  porta.
- **Nessuna autorizzazione.** Nessun ruolo, nessun perimetro per team, nessun
  controllo di proprietà.
- L'identità del revisore è una stringa fornita dal client (`demo.operator`). È
  registrata nell'audit trail ed è **completamente non verificata** — l'audit trail
  non è quindi a prova di manomissione e non reggerebbe come prova.
- Nessuna gestione di sessione, protezione CSRF o rate limiting.

### Protezione dei dati — non a livello di produzione
- **Nessuna cifratura a riposo.** Postgres usa le impostazioni di default; nessuna
  cifratura a livello di colonna sui dati dei clienti.
- **Nessun TLS.** HTTP ovunque; lo stack compose non termina nulla.
- **Nessuna policy di conservazione o cancellazione dei dati.** Nulla scade. Il
  diritto alla cancellazione non è implementato — eliminare un cliente farebbe
  cascata, ma non esiste un processo, né una verifica, né un audit della
  cancellazione stessa.
- **Nessuna considerazione di DPA per il fornitore del modello.** In
  un'implementazione reale il contenuto dei messaggi dei clienti sarebbe inviato a
  terzi; questo richiede un accordo sul trattamento dei dati, una base giuridica
  documentata, garanzie di trasferimento e una decisione sugli endpoint a
  conservazione zero. Nulla di tutto ciò è affrontato qui.
- **Nessuna redazione dei dati personali prima delle chiamate esterne.** Il testo
  completo del messaggio e il contesto cliente vanno al fornitore così come sono.
- **Nessuna pseudonimizzazione o anonimizzazione.**

### Gestione dei segreti
- Variabili d'ambiente e un file `.env`. Nessun vault, nessuna rotazione, nessun
  perimetro per servizio, nessun rilevamento di fughe.

### Maturità operativa
- **Nessuna osservabilità di produzione** — niente OpenTelemetry, nessun backend di
  metriche, nessun sistema di allarme, nessuna dashboard. Il logging è solo su
  stdout.
- **Nessun backup, nessun disaster recovery, nessun ripristino testato.**
- **Nessuna pipeline CI/CD**, nessuna scansione automatica di dipendenze o
  container.
- **Nessun penetration test, nessun modello di minaccia, nessuna revisione di
  sicurezza.**
- **Nessun rate limiting o controllo di quota** sugli endpoint AI — un endpoint
  aperto e non autenticato che spende denaro a ogni chiamata è un vettore di abuso
  reale.
- **Nessun caricamento di file**, quindi nessuna scansione malware — ma si noti che
  un flusso sinistri reale *richiede* caricamenti, e quella è una superficie di
  sicurezza significativa che questo POC non tocca.
- **Nessuna multi-tenancy.** Un solo broker, un solo database, nessun isolamento.
- **Nessuna alta disponibilità.** Una singola istanza di tutto; l'analisi gira in
  modo sincrono dentro la richiesta.

### Lacune specifiche dell'AI
- **Le euristiche anti-injection non sono un confine di sicurezza.** Sono regex e
  possono essere aggirate parafrasando. La protezione vera è il modello dati, non i
  pattern.
- **Nessuna moderazione dell'output** oltre ai controlli di ancoraggio.
- **Nessun failover del fornitore, circuit breaker o tetto di budget.**
- **Il motore di regole in modalità demo non è AI** ed è etichettato come tale
  ovunque compaia — nell'API (`demo_mode: true`), su ogni analisi memorizzata, e
  come banner permanente nell'interfaccia.
- **Gli embedding locali basati su hashing sono lessicali, non semantici.**
  Dimostrano la pipeline; non dimostrano il recupero semantico.
- **La qualità del recupero non è misurata.** Nessun recall@k, nessun insieme di
  rilevanza etichettato.

---

## 4. Note sulle minacce

| Preoccupazione | Stato attuale |
|---|---|
| **Prompt injection → esfiltrazione di dati** | Mitigata strutturalmente: nessun percorso di codice legge i dati di un altro cliente, e il modello non ha strumenti. Le euristiche aggiungono rilevamento ed escalation. Testata. |
| **Prompt injection → bozza dannosa** | Mitigata dalla revisione umana; un messaggio segnalato non produce mai una bozza auto-approvabile. |
| **Fatti di polizza allucinati** | Mitigata da ancoraggio, verifica lato server delle citazioni, rifiuto esplicito e un prompt che vieta di dichiarare termini di copertura non verificati. Non eliminata — un modello può comunque parafrasare male un chunk recuperato, motivo per cui approva un umano. |
| **Accesso non autorizzato** | **Non mitigata.** Non esiste autenticazione. |
| **Abuso di costo** | **Non mitigata.** Nessun rate limiting o tetto di budget. |
| **Manomissione dell'audit** | **Non mitigata.** L'identità del revisore non è verificata; i log sono righe ordinarie. |
| **Esposizione dei dati a riposo** | **Non mitigata.** Nessuna cifratura. |

---

## 5. Lavoro minimo prima di qualsiasi dato reale

Ordinato per dipendenza, non per preferenza:

1. **Autenticazione e autorizzazione** — SSO, RBAC per team, identità del revisore
   derivata dal server. Nient'altro conta finché questo non esiste.
2. **TLS ovunque**, cifratura a riposo, segreti in un vault gestito.
3. **Fondamenta legali** — DPA con il fornitore del modello, base giuridica,
   registri dei trattamenti, calendario di conservazione, processo per il diritto
   alla cancellazione, DPIA.
4. **Minimizzazione dei dati personali prima delle chiamate esterne** — redigere
   ciò di cui il modello non ha bisogno.
5. **Rate limiting e tetti di budget** sugli endpoint AI.
6. **Audit a prova di manomissione** — storage in sola aggiunta, identità
   verificata.
7. **Osservabilità di produzione** — tracce, metriche, allarmi sui fallimenti AI e
   sulla deriva del tasso di approvazione.
8. **Revisione di sicurezza** — modello di minaccia, scansione di dipendenze e
   container, penetration test.
9. **Backup con ripristino testato.**
10. **Valutazione su dati reali annotati**, con gate in CI sulla metrica di
    sicurezza.

---

## 6. Riepilogo onesto

Questo progetto dimostra che so progettare e costruire un flusso di lavoro
aziendale abilitato dall'AI con output strutturati, guardrail deterministici,
ancoraggio tramite recupero, supervisione umana, valutazione e tracciabilità.

**Non** dimostra un sistema pronto per la produzione, sicuro e conforme, e non
pretende di farlo. La distanza fra i due è esattamente quella che §3 e §5
enumerano — ed essere in grado di nominare quella distanza con precisione è, direi,
parte del punto.
