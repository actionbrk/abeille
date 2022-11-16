class SaveResult:
    def __init__(self):
        self.trouves = 0
        self.sauves = 0
        self.deja_sauves = 0
        self.from_bot = 0

    def __str__(self) -> str:
        return f"{self.sauves} enregistrés sur {self.trouves} trouvés ({self.from_bot} provenant de bots, {self.deja_sauves} déjà enregistrés)"
