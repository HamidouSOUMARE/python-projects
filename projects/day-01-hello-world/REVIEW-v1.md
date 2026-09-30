# Revue - Jour 01 - Hello World (v1)

**Note : 9.2/20** - Le besoin est couvert partiellement

Note brute 9.2/20, malus indices -0, seuil de validation 14.0/20.

## Verdict

Premiere tentative sur ce projet, donc aucun axe anterieur a verifier. Le coeur du besoin fonctionnel est atteint : le print() affiche un message identique a chaque lancement, sans jargon technique, et se termine seul sans jamais planter (ac1, ac2, ac3, ac5 sont couverts sur le fond). Le point bloquant est la livraison elle-meme : le README indique 'python main.py' alors que le fichier livre s'appelle 'helloword.py' (avec une faute de frappe dans le nom), ce qui va concretement empecher l'organisateur de lancer le programme du premier coup devant ses apprenants -- exactement le scenario qu'il redoute. La documentation est par ailleurs a l'etat de brouillon ('_A completer_'), et aucune verification n'est faite quant a l'affichage correct des accents sur Windows, alors que la compatibilite Windows/Mac est un critere critique explicite du brief. Le rendu est fonctionnellement proche du besoin mais souffre d'un manque de rigueur dans la finition qui menace directement l'usage reel prevu.</summary_md>
<parameter name="strengths">["Le message respecte le ton chaleureux et accessible demande, sans aucun jargon technique.", "Le comportement du script garantit par construction un affichage identique et sans erreur a chaque relance, meme repetee."]

## Grille

| Critere | Note | Justification |
| --- | --- | --- |
| Conformite au besoin | 12/20 | Le message s'affiche bien et est identique a chaque execution (ac1, ac2, ac3), mais le README reference 'python main.py' alors que le fichier s'appelle 'helloword.py' (typo en plus), ce qui casse la promesse 'pret a l'emploi tres rapidement' pour une association qui n'a jamais ouvert un terminal. |
| Structure et conception | 8/20 | Il s'agit d'une seule ligne de print sans aucune fonction ni point d'entree structure ; pour un besoin aussi minimal ce n'est pas forcement disqualifiant, mais l'absence totale d'organisation (pas de fonction main, pas de if __name__) ne montre aucune intention de conception. |
| Lisibilite et style | 10/20 | Le code est court et lisible, mais la faute de frappe 'bienvenu' au lieu de 'bienvenue' et le nom de fichier 'helloword.py' (au lieu de 'helloworld.py') nuisent a l'image professionnelle attendue face aux apprenants. |
| Robustesse | 10/20 | Un simple print() ne peut techniquement pas planter et se termine seul, ce qui satisfait ac3 et ac5 par defaut, mais rien n'est fait pour garantir explicitement l'encodage (accents) sur toutes les configurations Windows, un point sensible historiquement sur cet OS. |
| Idiomatismes Python | 8/20 | Aucun usage du bloc 'if __name__ == "__main__":', aucune annotation, aucune fonction encapsulant la logique d'affichage : le script est fonctionnel mais n'illustre aucun idiome Python meme basique. |
| Tests et documentation | 4/20 | Aucun test n'est fourni et le README renvoie a une section 'Choix techniques' explicitement laissee vide ('_A completer_'), en plus de contenir une commande de lancement incorrecte. |

## Points forts


## Axes d'amelioration

### 1. Faire correspondre exactement le nom du fichier et la commande documentee (priorite 1, conformite)

**Pourquoi :** Un formateur non technique qui suit le README a la lettre tapera 'python main.py' et obtiendra une erreur 'fichier introuvable', ce qui est le pire scenario possible pour ce brief.

**Comment :** Renommer le script en un nom clair sans faute (par exemple welcome.py ou main.py) et verifier que la commande ecrite dans le README correspond exactement au nom reel du fichier livre.

### 2. Completer reellement le README avant livraison (priorite 2, tests_doc)

**Pourquoi :** Le client a une contrainte de delai serre et compte sur la documentation pour lancer le programme seul ; une section 'A completer' laissee vide donne l'impression d'un livrable non fini.

**Comment :** Rediger quelques lignes expliquant comment lancer le script sur Windows et sur Mac (ex: 'python3' vs 'python'), et mentionner qu'aucune installation n'est necessaire hormis Python.

### 3. Encapsuler l'affichage dans une fonction avec un point d'entree explicite (priorite 3, structure)

**Pourquoi :** Structurer meme un script minimal avec une fonction main() et le bloc 'if __name__ == "__main__":' est une bonne pratique Python de base qui facilitera l'ajout de tests ou d'evolutions futures sans tout reecrire.

**Comment :** Deplacer le print() dans une fonction dediee (ex: afficher_message_bienvenue()) puis l'appeler depuis le bloc d'entree standard du script.

### 4. Verifier l'encodage des accents sur Windows (priorite 3, robustesse)

**Pourquoi :** Le brief insiste sur la compatibilite Windows/Mac sans configuration supplementaire, or certains terminaux Windows anciens affichent mal les caracteres accentues sans configuration prealable de l'encodage.

**Comment :** Tester le script sur une invite de commandes Windows standard et, si besoin, forcer l'encodage UTF-8 en sortie ou documenter la commande 'chcp 65001' a executer avant le lancement.

### 5. Corriger la faute d'orthographe dans le message affiche (priorite 3, lisibilite)

**Pourquoi :** Le tout premier contact des apprenants avec l'informatique doit degager une image soignee et professionnelle ; une faute visible ('bienvenu' au lieu de 'bienvenue') nuit a cette premiere impression.

**Comment :** Relire attentivement le texte affiche avant livraison, eventuellement le faire relire par une tierce personne.

