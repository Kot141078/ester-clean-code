# C0/skripts/gen_zhvt_secret.ps1 - convenient secret generation wrapper for Windows PowerShell
# Bridges: (Explicit) Enderton - parameter predicates; (Hidden) Ashby is a simple regulator; Janes is a priori of safety.
# Earth paragraph: secure entry in .env only when explicitly instructed.
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
