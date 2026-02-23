# S0/scripts/gen_jwt_secret.ps1 — udobnaya obertka generatsii sekreta dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty parametrov; (Skrytye) Ashbi — prostoy regulyator; Dzheynes — apriory bezopasnosti.
# Zemnoy abzats: bezopasnaya zapis v .env tolko po yavnomu ukazaniyu.
# c=a+b

param(
  [int]$Length = 64,
  [ValidateSet("base64url","hex","alnum")]
  [string]$Mode = "base64url",
  [string]$Dotenv = ""
)

if ($Dotenv -ne "") {
  python tools/gen_jwt_secret.py --length $Length --mode $Mode --write-dotenv $Dotenv
} else {
  python tools/gen_jwt_secret.py --length $Length --mode $Mode
}
