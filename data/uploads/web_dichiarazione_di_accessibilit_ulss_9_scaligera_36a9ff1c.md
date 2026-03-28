# Dichiarazione di accessibilità ULSS 9 Scaligera

*Fonte: https://www.aulss9.veneto.it/index.cfm?action=mys.page&content_id=2004*

## Dichiarazione di accessibilità

Questo sito è stato realizzato in ottemperanza dei 22 requisiti della Verifica Tecnica (D.M. 8/7/2005 - Allegato A) della Legge 4/2004 - Disposizioni per favorire l'accesso dei soggetti disabili agli strumenti informatici  
Regione del Veneto - ULSS 9 Scaligera - Dichiarazione di accessibilità AgID  
Obiettivi di accessibilità AGID  
  
Di seguito riportiamo i 22 punti di controllo con indicazione delle modalità con le quali sono stati soddifatti i requisiti di accessibilità e le tecniche di verifica che sono state adottate.  
  
**Requisito n. 1**  
Enunciato: Realizzare le pagine e gli oggetti al loro interno utilizzando tecnologie definite da grammatiche formali pubblicate nelle versioni più recenti disponibili quando sono supportate dai programmi utente. Utilizzare elementi ed attributi in modo conforme alle specifiche, rispettandone l'aspetto semantico. In particolare, per i linguaggi a marcatori HTML (HypertText Markup Language) e XHTML (eXtensible HyperText Markup Language):  
per tutti i siti di nuova realizzazione utilizzare almeno la versione 4.01 dell'HTML o preferibilmente la versione 1.0 dell'XHTML, in ogni caso con DTD (Document Type Definition - Definizione del Tipo di Documento) di tipo Strict;  
per i siti esistenti, in sede di prima applicazione, nel caso in cui non sia possibile ottemperare al punto a) è consentito utilizzare la versione dei linguaggi sopra indicati con DTD Transitional, ma con le seguenti avvertenze:  
evitare di utilizzare, all'interno del linguaggio a marcatori con il quale la pagina è realizzata, elementi ed attributi per definirne le caratteristiche di presentazione della pagina (per esempio, caratteristiche dei caratteri del testo, colori del testo stesso e dello sfondo, ecc.), ricorrendo invece ai Fogli di Stile CSS (Cascading Style Sheets) per ottenere lo stesso effetto grafico;  
evitare la generazione di nuove finestre; ove ciò non fosse possibile, avvisare esplicitamente l'utente del cambiamento del focus;  
pianificare la transizione dell'intero sito alla versione con DTD Strict del linguaggio utilizzato, dandone comunicazione alla Presidenza del Consiglio dei Ministri - Dipartimento per l'innovazione e le tecnologie e al Centro nazionale per l'informatica nella pubblica amministrazione.  
Metodologia di raggiungimento dell'obiettivo: il sito è realizzato attraverso il CMS per siti accessibili Webquality che genera automaticamente pagine HTML valide.  
Tecnica di verifica: Tutte le pagine sono state validate con il Validatore del W3C (http://validator.w3.org). Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 2**  
Enunciato: Non è consentito l'uso dei frame nella realizzazione di nuovi siti. In sede di prima applicazione, per i siti Web esistenti già realizzati con frame è consentito l'uso di HTML 4.01 o XHTML 1.0 con DTD frameset, ma con le seguenti avvertenze:  
evitare di utilizzare, all'interno del linguaggio a marcatori con il quale la pagina è realizzata, elementi ed attributi per definirne le caratteristiche di presentazione della pagina (per esempio, caratteristiche dei caratteri del testo, colori del testo stesso e dello sfondo, ecc.), ricorrendo invece ai Fogli di Stile CSS (Cascading Style Sheets) per ottenere lo stesso effetto grafico;  
fare in modo che ogni frame abbia un titolo significativo per facilitarne l'identificazione e la navigazione; se necessario, descrivere anche lo scopo dei frame e la loro relazione;  
pianificare la transizione a XHTML almeno nella versione 1.0 con DTD Strict dell'intero sito dandone comunicazione alla Presidenza del Consiglio dei Ministri - Presidenza del Consiglio dei Ministri - Dipartimento per l'innovazione e le tecnologie e alCentro nazionale per l'informatica nella pubblica amministrazione.  
Metodologia di raggiungimento dell'obiettivo: Con il CMS per siti accessibili Webquality non è possibile realizzare siti basati su Frame: ne risulta che ogni sito basato su Webquality risponde al Requisito 2. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 3**  
Enunciato: Fornire una alternativa testuale equivalente per ogni oggetto non di testo presente in una pagina e garantire che quando il contenuto non testuale di un oggetto cambia dinamicamente vengano aggiornati anche i relativi contenuti equivalenti predisposti; l'alternativa testuale equivalente di un oggetto non testuale deve essere commisurata alla funzione esercitata dall'oggetto originale nello specifico contesto.  
Metodologia di raggiungimento dell'obiettivo: Ogni oggetto immagine presente dispone di un campo testuale (attributo ALT). Gli oggetti multimediali dispongono di un campo testo per inserire il transcript del contenuto multimediale (sia esso un filmato, un file audio o altro ancora).  
Tecnica di verifica: attraverso vari software di validazione  abbiamo verificato la presenza del campo ALT in tutte le immagini. I singoli autori dei contenuti hanno verificato la correttezza logica delle descrizioni inserite. Attraverso un nuovo strumento di analisi offerto dal CMS Webquality sono state controllate, attraverso un report riassuntivo per l'intero sito, tutte le descrizioni di immagini e contenuti multimediali. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
  
**Requisito n. 4**  
Enunciato: Garantire che tutti gli elementi informativi e tutte le funzionalità siano disponibili anche in assenza del particolare colore utilizzato per presentarli nella pagina.  
Metodologia di raggiungimento dell'obiettivo: attraverso il CMS Webquality gli elementi della interfaccia sono personalizzati sia in termini grafici che di codice; ad esempio la voce corrente dei menu di navigazione è identificata sia con un colore diverso sia con l'uso del tag strong. Inoltre gli autori del sito hanno evitato, frasi del tipo "guarda il box rosso" perchè sarebbero prive di significato per non vedenti e persone con disabilità nella percezione dei colori.  
Tecnica di verifica: Esame a campione delle pagine del sito.   
  
**Requisito n. 5**  
Enunciato: Evitare oggetti e scritte lampeggianti o in movimento le cui frequenze di intermittenza possano provocare disturbi da epilessia fotosensibile o disturbi della concentrazione, ovvero possano causare il malfunzionamento delle tecnologie assistive utilizzate; qualora esigenze informative richiedano comunque il loro utilizzo, avvertire l'utente del possibile rischio prima di presentarli e predisporre metodi che consentano di evitare tali elementi.  
Metodologia di raggiungimento dell'obiettivo: E' stato insegnato agli autori dei contenuti di evitare immagini animate ed animazioni flash se non strettamente necessari e comunque mai "lampeggianti".  
Tecnica di verifica: Esame a campione delle pagine del sito.  
  
**Requisito n. 6**  
Enunciato: Garantire che siano sempre distinguibili il contenuto informativo (foreground) e lo sfondo (background), ricorrendo a un sufficiente contrasto (nel caso del testo) o a differenti livelli sonori (in caso di parlato con sottofondo musicale); evitare di presentare testi in forma di immagini; ove non sia possibile, ricorrere agli stessi criteri di distinguibilità indicati in precedenza.  
Metodologia di raggiungimento dell' obiettivo: In questo sito l'aspetto delle pagine e degli oggetti che le compongono (titoli, paragrafi, ecc.) è definito in modo centralizzato attraverso i CSS. In questo modo, pur lasciando la massima flessibilità di impaginazione di ogni singola pagina, si assicura la coerenza grafica dell'intero sito.  
Tecnica di verifica: La grafica utilizzata da questo sito è stata verificata applicando le formule W3C attraverso lo strumento di validazione WebAim (https://webaim.org/resources/contrastchecker/)  
  
**Requisito n. 7**  
Enunciato: Utilizzare mappe immagine sensibili di tipo lato client piuttosto che lato server, salvo il caso in cui le zone sensibili non possano essere definite con una delle forme geometriche predefinite indicate nella DTD adottata.  
Metodologia di raggiungimento dell'obiettivo: L'intefaccia Webquality supporta mappe immagini lato client come richiesto dalla normativa. In questo sito si è preferito non iserirne. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 8**  
Enunciato: In caso di utilizzo di mappe immagine lato server, fornire i collegamenti di testo alternativi necessari per ottenere tutte le informazioni o i servizi raggiungibili interagendo direttamente con la mappa.  
Metodologia di raggiungimento dell'obiettivo: L'intefaccia Webquality non supporta mappe immagini lato server, quindi non è possibile ad un utente finale di inserirne, ma solo all'amministratore del sito. In questo sito si è preferito non iserirne. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 9**  
Enunciato: Per le tabelle dati usare gli elementi (marcatori) e gli attributi previsti dalla DTD adottata per descrivere i contenuti e identificare le intestazioni di righe e colonne.  
Metodologia di raggiungimento dell'obiettivo: L'editor di Webquality supporta tabelle dati ad un livello logico (N righe per M colonne) e consente di specificare le intestazioni di riga e/o di colonna generando automaticamente tag TH al posto dei tag TD per le celle di intestazione. Per ogni tabella dati è possibile specificare il sommario (attributo SUMMARY). E' possibile importare con una sola operazione di copia ed incolla intere tabelle dati da Word, Excel, WordPerfect o altri software di Office Automation: Webquality riconosce il numero di righe e colonne ed incolla i valori delle celle eliminando gli eventuali attributi di formattazione così da formattare i dati con il solo uso dei CSS centralizzati.  
Tecnica di verifica: La pagina viene poi validata con il Validatore del W3C.Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 10**  
Enunciato: Per le tabelle dati usare gli elementi (marcatori) e gli attributi previsti nella DTD adottata per associare le celle di dati e le celle di intestazione che hanno due o più livelli logici di intestazione di righe o colonne.  
Metodologia di raggiungimento dell'obiettivo: L'editor di Webquality non supporta tabelle aventi più di un livello logico. Nel caso sia indispensabile utilizzarle è possibile importare pagine o porzioni di pagine xhtml contenenti tabelle accessibili a più livelli logici.  
Tecnica di verifica: La pagina viene poi validata con il Validatore del W3C. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 11**  
Enunciato: Usare i fogli di stile per controllare la presentazione dei contenuti e organizzare le pagine in modo che possano essere lette anche quando i fogli di stile siano disabilitati o non supportati.  
Metodologia di raggiungimento dell'obiettivo: L'impaginazione del sito è realizzata attraverso fogli di stile e senza l'uso di tabelle. I telai generali, poichè realizzati in HTML , possono essere impaginati con CSS o tabelle mentre il contenuto della pagina, generato direttamente dal motore di Webquality, è privo di tabelle.  
Webquality utilizza sempre i tag più appropriati per ogni situazione: H1 per i titoli, H2 per i sottotitoli, P per i paragrafi, OL per gli elenchi, STRONG ed EM per l'evidenziazione del testo: in questo modo anche disabilitando i fogli di stile le pagine possono essere lette senza problemi e conservano in modo completo il contenuto informativo e logico strutturale.  
Tecnica di verifica: La pagina viene poi validata con il Validatore del W3C (http://jigsaw.w3.org/css-validator/) e vengono anche disabilitati i fogli stile, manualmente, per constatare che le pagine non abbiano problemi e possano essere lette correttamente. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 12**  
Enunciato: La presentazione e i contenuti testuali di una pagina devono potersi adattare alle dimensioni della finestra del browser utilizzata dall'utente senza sovrapposizione degli oggetti presenti o perdita di informazioni tali da rendere incomprensibile il contenuto, anche in caso di ridimensionamento, ingrandimento o riduzione dell'area di visualizzazione o dei caratteri rispetto ai valori predefiniti di tali parametri.  
Metodologia di raggiungimento dell'obiettivo: I contenuti sono perfettamente liquidi ed impaginati con CSS. L'area contenuti di ogni pagina è perfettamente liquida e ridimensionabile. WebQuality è in grado di fornire css responsive capace di adattarsi automaticamente a ogni dispositivo e a ogni risoluzione offrendo sempre l'aspetto migliore possibile dato il contesto, ovviamente tutto il css utilizzato per raggiungere tale scopo è sempre conforme alle specifiche CSS.  
Tecnica di verifica: Le pagine viengono poi validate con il Validatore del W3C. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 13**  
Enunciato: In caso di utilizzo di tabelle a scopo di impaginazione, garantire che il contenuto della tabella sia comprensibile anche quando questa viene letta in modo linearizzato e utilizzare gli elementi e gli attributi di una tabella rispettandone il valore semantico definito nella specifica del linguaggio a marcatori utilizzato.  
Metodologia di raggiungimento dell'obiettivo: L'impaginazione generale di ogni pagina è realizzata attraverso porzioni di HTML e CSS (telai) realizzati da chi progetta il sito. E' quindi possibile realizzare sia siti impaginati con tabelle che siti impaginati esclusivamente con i CSS.  
Tecnica di verifica: Le pagine viengono poi validate con il Validatore del W3C. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 14**  
Enunciato: Nei moduli (form), associare in maniera esplicita le etichette ai rispettivi controlli, posizionandole in modo che sia agevolata la compilazione dei campi da parte di chi utilizza le tecnologie assistive.  
Metodologia di raggiungimento dell'obiettivo: E' possibile realizzare form anche molto complessi senza la necessità di conoscere alcun linguaggio di programmazione. Nell'editor visuale di Webquality si inseriscono gli oggetti base del form (quali campi di testo, menu a discesa, ecc) ed in fase di pubblicazione WebQuality genera automaticamente il codice utilizzando correttamente il campo LABEL per ogni elemento del Form.  
Tecnica di verifica: I moduli vengono poi validati con il Validatore del W3C. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 15**  
Enunciato: Garantire che le pagine siano utilizzabili quando script, applet, o altri oggetti di programmazione sono disabilitati oppure non supportati; ove ciò non sia possibile fornire una spiegazione testuale della funzionalità svolta e garantire una alternativa testuale equivalente, in modo analogo a quanto indicato nel requisito n. 3.  
Metodologia di raggiungimento dell'obiettivo: L'uitlizzo di codice client side è stato ridotto il più possibile relegandolo dove possibile al solo ruolo estetico, costituiscono eccezione il plugin per la traduzione del sito di google e la distribuzione di contenuti video tramite youtube  
Tecnica di verifica: Esame manuale delle pagine del sito. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 16**  
Enunciato: Garantire che i gestori di eventi che attivano script, applet o altri oggetti di programmazione o che possiedono una propria specifica interfaccia, siano indipendenti da uno specifico dispositivo di input.  
Metodologia di raggiungimento dell'obiettivo: Gli elementi javascript utilizzati non hanno mai generato problemi conosciuti con alcun dispositivo di input,. Nonostante i numerosi test effettuati, nel caso si dovessero evidenziare incompatibilità legate a queste funzioni sarà sufficiente modificare il motore di Webquality per risolvere il problema in tutti i siti realizzati con Webquality.  
Tecnica di verifica: Esame manuale delle pagine del sito. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 17**  
Enunciato: Garantire che le funzionalità e le informazioni veicolate per mezzo di oggetti di programmazione, oggetti che utilizzano tecnologie non definite da grammatiche formali pubblicate, script e applet siano direttamente accessibili.  
Metodologia di raggiungimento dell'obiettivo: Il sito non utilizza tecnologie non definite da grammatiche formali pubblicate, script e applet  
Tecnica di verifica: Esame manuale delle pagine del sito. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 18**  
Enunciato: Nel caso in cui un filmato o una presentazione multimediale siano indispensabili per la completezza dell'informazione fornita o del servizio erogato, predisporre una alternativa testuale equivalente, sincronizzata in forma di sotto-titolazione o di descrizione vocale, oppure fornire un riassunto o una semplice etichetta per ciascun elemento video o multimediale tenendo conto del livello di importanza e delle difficoltà di realizzazione nel caso di trasmissioni in tempo reale.  
Metodologia di raggiungimento dell'obiettivo: Gli oggetti multimediali inseribili prevedono un campo testuale esteso ove inserire la descrizione dei contenuti multimediali stessi, in alternativa WebQuality mette a disposizione un plugin di collegamento per i video ospitati da YouTube  
Tecnica di verifica: Esame manuale delle pagine del sito. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 19**  
Enunciato: Rendere chiara la destinazione di ciascun collegamento ipertestuale (link) con testi significativi anche se letti indipendentemente dal proprio contesto oppure associare ai collegamenti testi alternativi che possiedano analoghe caratteristiche esplicative, nonché prevedere meccanismi che consentano di evitare la lettura ripetitiva di sequenze di collegamenti comuni a più pagine.  
Metodologia di raggiungimento dell'obiettivo: Nel sito la descrizione dei link è demandata agli autori dei contenuti e non potrebbe essere altrimenti. Chi progetta i modelli grafici generali del sito può inserirvi opportuni link al fine di saltare a determinati punti della pagina. Il sito supporta i tasti di accesso rapido (AccessKey) consentendo agli autori del sito di associarli opportunamente a specifiche voci di menu.  
Tecnica di verifica: attraverso il software di validazione Vamolà abbiamo verificato i collegamenti ipertestuali. I singoli autori dei contenuti hanno verificato la correttezza logica delle descrizioni inserite. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 20**  
Enunciato: Nel caso che per la fruizione del servizio erogato in una pagina è previsto un intervallo di tempo predefinito entro il quale eseguire determinate azioni, è necessario avvisare esplicitamente l'utente, indicando il tempo massimo consentito e le alternative per fruire del servizio stesso.  
Metodologia di raggiungimento dell'obiettivo: Webquality non prevede nessuna funzionalità a tempo. Nel caso si integrino in un sito basato su Webquality applicazioni che prevedono un determinato intervallo di tempo per il compimento di determinate azioni i responsabili della integrazione dovranno avere cura di inserire opportuno avviso.  
Tecnica di verifica: Esame manuale delle pagine del sito. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 21**  
Enunciato: Rendere selezionabili e attivabili tramite comandi da tastiere o tecnologie in emulazione di tastiera o tramite sistemi di puntamento diversi dal mouse i collegamenti presenti in una pagina; per facilitare la selezione e l'attivazione dei collegamenti presenti in una pagina è necessario garantire che la distanza verticale di liste di link e la spaziatura orizzontale tra link consecutivi sia di almeno 0,5 em, le distanze orizzontale e verticale tra i pulsanti di un modulo sia di almeno 0,5 em e che le dimensioni dei pulsanti in un modulo siano tali da rendere chiaramente leggibile l'etichetta in essi contenuta.  
Metodologia di raggiungimento dell'obiettivo: Tutti i link generati, siano essi link interni all'area contenuti di ogni pagina o link appartenenti ad indici di navigazione sono perfettamente selezionabili con ogni dispositivo. Nel sito, infatti, non viene utilizzato javascript java o flash e quindi ogni link è in puro html. La spaziatura ed il posizionamento di link, pulsanti e campi dei form è definita in modo centralizzato attraverso fogli di stile CSS, semplificando così il raggiungimento dei requisiti del punto 21.  
Tecnica di verifica: Esame manuale delle pagine del sito. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Requisito n. 22**  
Enunciato: Per le pagine di siti esistenti che non possano rispettare i suelencati requisiti (pagine non accessibili), in sede di prima applicazione, fornire il collegamento a una pagina conforme a tali requisiti, recante informazioni e funzionalità equivalenti a quelle della pagina non accessibile ed aggiornata con la stessa frequenza, evitando la creazione di pagine di solo testo; il collegamento alla pagina conforme deve essere proposto in modo evidente all'inizio della pagina non accessibile.  
Metodologia di raggiungimento dell'obiettivo: Il sito è conforme a tutti i punti della presente Verifica Tecnica e non è quindi necessario realizzare versioni alternative delle pagine stesse. Sono state seguite le linee guida del modello di autovalutazione dell'AGID (Allegato 2 alle linee guida sull’accessibilità degli strumenti informatici)  
  
**Aiutateci a migliorare**  
Nonostante l'attenzione posta nella realizzazione del sito ed i numerosi test condotti non è possibile escludere con certezza che una o più pagine siano a nostra insaputa ancora inaccessibili ad alcune categorie di utenti.  
In questo caso ci scusiamo fin d'ora e vi preghiamo di segnalare ogni irregolarità riscontrata a: innovazioni@aulss9.veneto.it, al fine di consentirci di eliminarla nel più breve tempo possibile.
