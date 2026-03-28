# Indicazioni Ordine NSO in Fattura Elettronica ULSS 9 Scaligera

*Fonte: https://www.aulss9.veneto.it/index.cfm?action=mys.page&content_id=2006*

A seguito di quanto disposto dal decreto MEF del 7 dicembre 2018 integrato dal decreto MEF del 27 dicembre 2019, si rende noto che

* a partire dal **1° gennaio 2021**, gli enti del SSN e i soggetti che effettuano acquisti per loro conto non potranno dar corso alla liquidazione e al successivo pagamento di Fatture elettroniche relative all’acquisto di **beni sanitari e non sanitari** che non riportino il riferimento al documento d’Ordine che le ha generate;
* a partire dal **1° gennaio 2022**, gli enti del SSN e i soggetti che effettuano acquisti per loro conto non potranno dar corso alla liquidazione e al successivo pagamento di Fatture elettroniche relative all’acquisto di **servizi sanitari e non sanitari** che non riportino il riferimento al documento d’Ordine che le ha generate

A tal fine, si puntualizzano alcune indicazioni tecniche da seguire.  
In base a quanto riportato nel documento di Regole Tecniche, il riferimento dell’Ordine elettronico è rappresentato dalla c.d. “**Tripletta d’identificazione**”, costituita  dall’identificativo dell’Ordine (ID), dalla data di emissione dell’Ordine e dall’identificativo del mittente.  
Al fine di supportarvi nel corretto adempimento dell’obbligo, si ricorda che, per le Fatture riferite a Ordini di beni e servizi, queste informazioni dovranno essere obbligatoriamente indicate nei seguenti campi previsti dal formato FatturaPA:

* l’**Identificativo dell’Ordine** deve essere inserito nel campo 2.1.2.2 <IdDocumento>
* la **data di emissione dell’Ordine** deve essere inserita nel campo 2.1.2.3 <Data>
* l’**Identificativo del mittente dell’Ordine** deve essere riportato nel campo 2.1.2.5 <CodiceCommessaConvenzione> preceduto e seguito dal carattere **“#”** senza interposizione di spazi.

Tali elementi sono rinvenibili nell’ordine NSO come di seguito indicato:  
**Identificativo ordine**  
**Data emissione ordine  
**Mittente dell’ordine in questo esempio 40ZDJM****  
 **Quindi nel caso dell’ordine citato nell’esemplificazione, la conseguente fattura deve  
riportare i seguenti dati:  
***FATTURA PA***  
***Dati dell'ordine di acquisto***** 

* ***Identificativo ordine di acquisto: 1-2021-1779***
* ***Data ordine di acquisto: 2021-01-12***
* ***Codice commessa/convenzione: #40ZDJM#***

 **Per ulteriori dettagli relativi all’ordine NSO visionare il sito del MEF : Clicca qui**
