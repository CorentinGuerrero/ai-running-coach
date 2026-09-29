# Le chat avec le coach

!!! info "Page provisoire"
    Cette page est un squelette laissé par la partie exploitation ; elle sera remplacée par
    la documentation complète du chat.

Le chat est un service optionnel du tableau de bord : vous parlez au coach depuis le
navigateur, il lit et écrit dans votre workspace comme en session normale, et toute
écriture vers Garmin ou Intervals.icu passe par une **approbation** de votre part.

C'est un front « maison » : il appelle le modèle avec une **clé API facturée au token**
(pas votre abonnement). Un plafond quotidien (`[chat].daily_budget_eur`) l'encadre.

## Activer

```bash
./install.sh --llm openrouter --chat     # ou --llm anthropic
```

- Réglages : [Configuration — `[chat]`](../configuration.md#le-chat-avec-le-coach-chat).
- Clé API : `~/.config/ai-running-coach/llm.env` (mode 600), jamais dans le TOML —
  voir [Le coach dans la poche](../mobile.md#synchronisation-sur-openrouter-ou-toute-api-compatible-openai).
- Service : `scripts/coach-chat.sh install|status|logs|uninstall`.
- Derrière Traefik et un SSO : `deploy/chat/traefik/README.md`.
- Diagnostic : `python3 scripts/coach_doctor.py --check chat_service`.
