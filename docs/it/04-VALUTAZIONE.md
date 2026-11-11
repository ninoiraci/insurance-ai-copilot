# Valutazione

*Traduzione italiana di [`docs/EVALUATION.md`](../EVALUATION.md).*

Una funzionalità AI senza valutazione è una demo, non un prodotto. Questo
documento descrive il dataset, cosa significa ogni metrica, quali sono i numeri
attuali e — cosa importante — cosa questa valutazione **non** può dirti.

---

## 1. Cosa viene valutato

**L'intero sistema decisionale, non la chiamata al modello.**

Ogni caso attraversa la stessa `AnalysisPipeline` che usa il prodotto:
classificazione → validazione dello schema → regole di business deterministiche →
gate di recupero → prossima azione migliore → gate di revisione. Valutare
l'output grezzo dell'LLM misurerebbe la cosa sbagliata, perché ciò che va in
produzione è la pipeline.

È per questo che `urgency_accuracy` è misurata *dopo* il motore di regole, e che
`action_accuracy` valuta l'output del motore di azioni e non il suggerimento del
modello.

---

## 2. Costruzione del dataset

`data/evaluation/evaluation_cases.json` — **60 casi etichettati**, tutti sintetici.

### Copertura

| Dimensione | Copertura |
|---|---|
| Intenti | Tutti e 12, minimo 3 casi ciascuno |
| Tipi assicurativi | MOTOR, HOME, HEALTH, LIFE, TRAVEL, BUSINESS, UNKNOWN |
| Canali | WhatsApp (brevi, informali), Email (lunghe, formali), trascrizioni telefoniche |
| Difficoltà | `STANDARD` · `AMBIGUOUS` · `HIGH_RISK` · `NOISY` · `ADVERSARIAL` |

### Casi deliberatamente difficili

Il dataset non è un percorso felice. Include:

- **Ambigui** — *«No me funciona lo del seguro»* («Non mi funziona la cosa
  dell'assicurazione»). Il comportamento corretto è confidenza bassa e una
  richiesta di chiarimento. Una classificazione sicura di sé qui è un **difetto**,
  e il dataset la valuta come tale.
- **Rumorosi** — abbreviazioni WhatsApp, accenti mancanti, emoji, frasi
  ininterrotte.
- **Di confine** — EV-031 chiede quali documenti servano per un sinistro da danno
  d'acqua *senza denunciare un sinistro*. Sia `DOCUMENT_REQUEST` sia `CLAIM` sono
  sostenibili; il caso esiste proprio per vedere da che parte pende un sistema.
- **Segnali in conflitto** — EV-047 menziona una doppia fatturazione ma l'intento
  dominante è un reclamo con escalation legale. La procedura interna di escalation
  dice che vincono i reclami; l'etichetta segue la procedura.
- **Avversari** — tre casi di prompt injection, incluso uno che mescola una domanda
  legittima con una injection.
- **Trappola nota di sovra-escalation** — EV-010 è una richiesta di *rimborso*
  sanitario che menziona un infortunio al ginocchio. Un sistema a parole chiave
  legge «lesión» ed escala a `CRITICAL`. L'etichetta è `MEDIUM`, quindi il costo
  della regola conservativa sui feriti viene misurato invece che nascosto.

### Metodo di etichettatura

Le etichette sono l'esito che sceglierebbe un operatore competente, seguendo le
procedure scritte del broker stesso in `data/knowledge_base/`. Dove un caso è
genuinamente ambiguo, il campo `notes` registra perché è stata scelta quella
etichetta.

Le entità attese sono **parziali per scelta**: sono etichettate solo le entità che
contano per l'instradamento. Un'entità predetta che il dataset non etichetta non
viene conteggiata come falso positivo.

---

## 3. Metriche

| Metrica | Definizione | Si legge come |
|---|---|---|
| `intent_accuracy` | Corrispondenza esatta su 12 etichette | Capisce cosa vuole il cliente? |
| `urgency_accuracy` | Corrispondenza esatta, **dopo** le regole di business | Il caso ottiene la priorità giusta? |
| `insurance_type_accuracy` | Corrispondenza esatta su 8 etichette | Identifica il prodotto? |
| `action_accuracy` | Corrispondenza esatta sulla decisione del motore di azioni | Succede la cosa giusta dopo? |
| `schema_validation_rate` | Quota di casi validati senza fallback | Affidabilità strutturale del livello AI |
| `entity_extraction.{precision,recall,f1}` | Sulle chiavi di entità etichettate | I fatti sono giusti? |
| **`human_review_recall_on_risky`** | Dei casi che **devono** arrivare a un umano, quanti sono stati segnalati | **La metrica di sicurezza** |
| `human_review_false_alarm_rate` | Dei casi sicuri, quanti sono stati segnalati inutilmente | Il costo della prudenza |
| `avg_latency_ms`, `p95_latency_ms` | Per caso, end-to-end | Fattibilità operativa |
| `total_input_tokens`, `total_output_tokens` | Consumo sommato | Base di costo (zero in modalità demo) |
| `intent_confusion` | Conteggi reale → predetto | *Dove* sbaglia, non solo quanto spesso |

### Perché il recall di revisione è la metrica che conta

Le metriche di accuratezza misurano l'utilità. **Il recall di revisione misura la
sicurezza.**

Un caso rischioso non intercettato significa che una bozza su un sinistro, una
disdetta o un pagamento potrebbe raggiungere un cliente senza che un umano l'abbia
letta. Ogni altra metrica può degradare con grazia; questa no. È il numero su cui
metterei un gate in CI.

La sua controparte, `human_review_false_alarm_rate`, è riportata accanto perché un
sistema che segnala tutto ottiene un perfetto 100 % di recall ed è inutile. La
coppia va letta insieme.

Il tasso di falsi allarmi attuale è **47,6 %**: circa metà dei casi che avrebbero
potuto essere auto-approvati in sicurezza vengono comunque instradati a un umano.
È un costo reale — è tempo di operatore — ed è la conseguenza diretta delle scelte
conservative del §4 (intenti ad alto rischio sempre rivisti, bozze non ancorate
sempre riviste). Se il 47,6 % sia accettabile è una decisione di business, non
tecnica; il punto di misurarlo è che il business può prendere quella decisione con
un numero davanti invece che con una sensazione.

### Confronto delle entità

Confronto di stringhe indulgente, perché *«1234ABC»* e *«1234 abc»* sono la stessa
targa: normalizzazione di maiuscole, rimozione degli spazi, con corrispondenza per
sottostringa per i valori più lunghi di tre caratteri (così `"ayer"` corrisponde a
`"ayer por la tarde"`).

---

## 4. Baseline attuale — modalità demo

Il motore di regole mock, 60 casi:

| Metrica | Risultato |
|---|---|
| Accuratezza intento | **91,7 %** |
| Accuratezza urgenza | 85,0 % |
| Accuratezza tipo assicurativo | 93,3 % |
| Accuratezza azione | **96,7 %** |
| Tasso di validazione dello schema | 100 % |
| F1 entità | 0,903 (P 0,824 / R 1,000) |
| **Recall revisione umana sui casi rischiosi** | **97,4 %** |
| Tasso di falsi allarmi della revisione umana | 47,6 % |
| Latenza media | ~100 ms |

**Leggili correttamente.** Questo è un matcher a parole chiave spagnole, non un
modello linguistico. È una *baseline* — il pavimento che un LLM reale deve
superare. Pubblicarla è deliberato: se un modello costoso non riesce a battere una
regex su questa tassonomia, è bene saperlo prima di mandarlo in produzione.

La validazione dello schema è banalmente al 100 % in modalità demo, dato che il
mock emette JSON valido per costruzione. Quel numero diventa significativo solo
con un fornitore reale.

### Fallimenti noti, e perché sono lasciati dentro

**L'unico caso rischioso non intercettato (EV-015).** Un cliente dice che la sua
polizza auto scade *fra quattro giorni*. Un annotatore umano lo legge e segna
`HIGH`. Il sistema no: l'urgenza di rinnovo è guidata dalla **data di scadenza nel
database**, e la valutazione gira deliberatamente senza contesto cliente. Dato il
contesto reale, `renewal_imminent` scatta correttamente — cosa coperta da uno unit
test.

Questo è un limite genuino e strutturale dell'impianto di valutazione, non un bug.
Riportare 97,4 % con una causa nominata è più utile che aggiustarlo al 100 %.

**Sovra-escalation (EV-010).** Il rimborso sanitario che menziona un infortunio al
ginocchio viene escalato a `CRITICAL` dalla regola conservativa sui feriti.
Atteso: `MEDIUM`. Questa è l'asimmetria dell'[02-ARCHITETTURA.md §5](02-ARCHITETTURA.md#5-perché-le-regole-deterministiche-completano-lllm)
che fa esattamente ciò per cui è stata pensata, e questo caso è il modo in cui il
suo costo viene misurato.

**Etichette di intento avversarie (EV-058/059/060).** Il prompt dice a un modello
reale di classificare le injection come `GENERAL_SUPPORT`; la baseline a parole
chiave non ha regole per il testo di injection in inglese e restituisce `UNKNOWN`.
Il comportamento di *sicurezza* è comunque corretto — tutti e tre escalano alla
compliance — quindi `action_accuracy` non è toccata mentre `intent_accuracy` ne
paga il prezzo. Etichette corrette per il prodotto, fallimento onesto per la
baseline.

---

## 5. Come eseguirla

```bash
# CLI
cd backend && FLASK_APP=app:create_app flask evaluate --label "prima del cambio prompt"

# API
curl -X POST localhost:5001/api/evaluations/run \
     -H 'Content-Type: application/json' -d '{"label":"esecuzione api"}'

# UI
Evaluations → Run evaluation
```

Le esecuzioni sono **persistite** (`evaluation_runs` + `evaluation_results`) così
che i cambi di prompt possano essere confrontati nel tempo. Questo è il flusso di
lavoro: cambia `classification_v1` → `classification_v2`, riesegui, confronta le
due righe nella tabella dello storico esecuzioni.

La tabella per caso mostra per default **solo i fallimenti**, perché è lì che sta
l'informazione.

---

## 6. Limiti della valutazione sintetica

Dichiarati senza giri di parole, perché contano più dei numeri:

1. **Ho scritto sia i casi sia il sistema.** Anche con attenzione, il dataset
   eredita le mie assunzioni su come scrivono i clienti. I messaggi reali saranno
   peggiori — più lunghi, più contraddittori, con tre richieste in un paragrafo.
2. **60 casi sono pochi.** L'accuratezza per intento poggia su 3–12 esempi, quindi
   le cifre individuali hanno intervalli di confidenza ampi. L'aggregato è
   indicativo, non preciso.
3. **Un solo annotatore, nessun accordo inter-annotatore.** Per casi genuinamente
   ambigui (EV-031, EV-049) un secondo annotatore probabilmente dissentirebbe, e
   qui non c'è modo di quantificarlo.
4. **Nessun contesto cliente**, come discusso sopra.
5. **La qualità della risposta non è valutata.** La pipeline è valutata su
   classificazione, instradamento e sicurezza. Se la bozza in spagnolo sia *buona*
   — tono, completezza, se soddisferebbe davvero un cliente — non è misurato
   affatto. Servirebbe una valutazione umana o una rubrica LLM-as-judge.
6. **La qualità del recupero non è valutata direttamente.** Non esiste un insieme
   etichettato query→chunk rilevante, quindi recall@k e MRR non sono calcolati. È
   visibile solo l'effetto a valle (ancorato o no).
7. **Nessuna ampiezza avversaria.** Tre casi di injection sono uno smoke test, non
   un red team.
8. **Costo e latenza non sono rappresentativi** in modalità demo: niente rete,
   niente token.
9. **L'esecutore è sincrono.** Avviare un'esecuzione completa da 60 casi
   dall'interfaccia tiene aperta la richiesta HTTP per tutta la sua durata. Va bene
   a ~6 s in modalità demo ma non con un modello reale, dove un'esecuzione richiede
   minuti e colpirà il timeout del proxy. Usa la CLI (`flask evaluate`) o passa un
   `limit` finché l'esecutore non verrà spostato su una coda di job.

---

## 7. Come evolverebbe con dati di produzione

1. **Sostituire i casi sintetici con casi reali campionati.** Stratificare per
   intento e canale, puntare a 500–1000 casi, e rietichettare con due annotatori
   più un arbitro. Tracciare il κ di Cohen.
2. **Estrarre etichette dal comportamento degli operatori.** Ogni
   `EDIT_AND_APPROVE` è un'etichetta gratuita: il diff fra la bozza AI e il testo
   inviato dice esattamente cosa non andava. Ogni `REJECT` con note è un
   fallimento etichettato. Questo è il dataset di maggior valore nel sistema e si
   accumula automaticamente — lo schema memorizza già entrambe le versioni.
3. **Aggiungere la valutazione del recupero.** Etichettare i chunk rilevanti per
   query; misurare recall@k, MRR e nDCG. Attualmente i fallimenti di recupero si
   travestono da fallimenti di generazione.
4. **Aggiungere la valutazione della qualità della risposta.** Una rubrica
   (accuratezza, completezza, tono, assenza di invenzioni) valutata da umani su un
   campione, più un giudice LLM validato contro quelle valutazioni prima di
   fidarsene su larga scala.
5. **Gate in CI.** Bloccare un cambio di prompt o modello che faccia scendere
   `human_review_recall_on_risky` sotto un pavimento concordato, o che sposti
   l'accuratezza di intento oltre un delta stabilito.
6. **Monitoraggio in produzione come valutazione continua.** Deriva della
   distribuzione di confidenza, deriva del tasso di approvazione per intento, tasso
   di modifica per intento, deriva del tasso di escalation. Un modello che degrada
   silenziosamente si manifesta qui molto prima che qualcuno presenti un reclamo.
7. **Metriche per fetta.** L'accuratezza complessiva nasconde il caso che conta.
   Riportare per intento, per canale e per lunghezza del messaggio — un sistema
   accurato al 95 % nel complesso e al 60 % sulle disdette ha un problema
   specifico e risolvibile.
