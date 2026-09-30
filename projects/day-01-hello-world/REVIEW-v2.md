# Revue - Jour 01 - Hello World (v2)

**Note : 13.45/20** - Fonctionnel, conception a retravailler

Note brute 13.45/20, malus indices -0, seuil de validation 14.0/20.

## Verdict

Ce rendu corrige efficacement les deux points les plus bloquants de la version precedente : le nom du fichier correspond desormais exactement a la commande documentee dans le README, et ce dernier a ete reellement complete avec les commandes Windows/Mac. La structure a egalement ete amelioree avec une fonction dediee et un point d'entree `if __name__ == "__main__"`, ce qui repond a l'axe de conception souleve. En revanche, deux axes restent ouverts : la faute d'orthographe 'bienvenu' (au lieu de 'bienvenue') est toujours presente, y compris dans le nom de la fonction, et aucune verification ni mention de l'encodage des accents sur Windows n'a ete ajoutee alors que c'est un point sensible pour un critere critique du brief (compatibilite Windows/Mac). L'absence totale de tests continue de plafonner la note sur ce critere. Le rendu est desormais livrable en l'etat pour l'usage prevu, mais une derniere relance de correction serait bienvenue avant la session de formation.</summary_md>
<parameter name="strengths">[
  "Le nom du fichier main.py correspond desormais exactement a la commande documentee dans le README, supprimant le risque d'erreur au lancement devant les apprenants.",
  "Le README a ete reellement redige avec les commandes distinctes pour Mac (python3) et Windows (python), repondant concretement a la contrainte de parc mixte.",
  "L'encapsulation dans une fonction et l'usage du bloc if __name__ == '__main__' donnent une base propre et evolutive malgre la simplicite du besoin."
]

## Grille

| Critere | Note | Justification |
| --- | --- | --- |
| Conformite au besoin | 15/20 | Le fichier s'appelle maintenant main.py et le README documente exactement 'python main.py', corrigeant le point bloquant precedent ; le message s'affiche identique a chaque lancement sans jargon (ac1, ac2, ac3, ac5). Cependant la faute d'orthographe 'bienvenu' au lieu de 'bienvenue' dans une fonction nommee message_bienvenu reste presente, ce qui degrade legerement la clarte attendue par ac1. |
| Structure et conception | 16/20 | L'axe demande a ete traite : la logique est encapsulee dans une fonction message_bienvenu() appelee depuis main(), avec le bloc if __name__ == '__main__' standard. Pour un script de cette taille c'est suffisant, meme si le nommage 'message_bienvenu' est un nom de variable plutot qu'un verbe d'action clair type 'afficher_message_bienvenue'. |
| Lisibilite et style | 11/20 | Le code est court et propre syntaxiquement (espace incoherent apres les deux-points dans 'def message_bienvenu(): ' mis a part), mais la faute d'orthographe explicitement signalee a la tentative precedente ('bienvenu' au lieu de 'bienvenue', y compris dans le nom de la fonction) n'a pas ete corrigee, ce qui etait un axe prioritaire identifie. |
| Robustesse | 12/20 | Un simple print() garantit mecaniquement l'absence de plantage et une terminaison propre (ac3, ac5), mais l'axe demande sur la verification de l'encodage des accents sous Windows n'a pas ete traite : aucune mention dans le README, aucun test documente, ce qui laisse un risque residuel sur un critere critique du brief (ac4). |
| Idiomatismes Python | 15/20 | Le script utilise desormais le bloc if __name__ == '__main__' et une fonction dediee, ce qui couvre les idiomes de base attendus pour ce niveau ; il manque toutefois des annotations de type simples (par ex. -> None) qui auraient ete un plus facile a ajouter. |
| Tests et documentation | 8/20 | Le README a ete complete avec les commandes exactes pour Windows et Mac ('python3 main.py' vs 'python main.py'), ce qui repond a l'axe demande, mais aucun test (meme minimal, comme un test unitaire capturant stdout) n'est fourni, ce qui plafonne la note sur ce critere. |

## Points forts


## Axes d'amelioration

### 1. Corriger la faute d'orthographe residuelle dans le message et le nom de fonction (priorite 1, lisibilite)

**Pourquoi :** Ce defaut avait deja ete signale et impacte directement la premiere impression professionnelle donnee aux apprenants, exactement le moment que le client veut soigner.

**Comment :** Relire le texte affiche mot a mot, renommer 'message_bienvenu' en quelque chose comme 'afficher_message_bienvenue', et faire relire par une tierce personne avant livraison finale.

### 2. Documenter ou tester explicitement le comportement des accents sur Windows (priorite 2, robustesse)

**Pourquoi :** La compatibilite Windows/Mac sans configuration est un critere critique du brief, et les terminaux Windows plus anciens peuvent mal afficher les caracteres accentues sans reglage prealable.

**Comment :** Tester le script sur une invite de commandes Windows standard (cmd et PowerShell) et, si un probleme apparait, ajouter une ligne dans le README expliquant la commande 'chcp 65001' ou forcer l'encodage UTF-8 en sortie dans le script.

### 3. Ajouter un test minimal capturant la sortie standard (priorite 3, tests_doc)

**Pourquoi :** Un projet sans aucun test reste plafonne sur ce critere meme si le README est correct ; un test simple donnerait une garantie automatisee que le message reste identique a chaque execution.

**Comment :** Utiliser capsys de pytest ou io.StringIO pour capturer la sortie de message_bienvenu() et verifier qu'elle correspond au texte attendu, dans un fichier test_main.py separe.

### 4. Nettoyer les petites incoherences de style (priorite 3, idiomes)

**Pourquoi :** L'espace superflu apres les deux-points dans la definition de fonction (PEP 8) est un detail mineur mais facile a corriger qui ameliore l'image de rigueur du livrable.

**Comment :** Passer le fichier dans un linter comme flake8 ou black pour detecter et corriger automatiquement ce type d'ecart avant chaque livraison.

