# sunskills

UBC Solar's [Claude Code plugin](https://docs.claude.com/en/docs/claude-code/plugins) marketplace.

## Install

```
/plugin marketplace add UBC-Solar/sunskills
/plugin install gbian-local-debug@sunskills
/plugin install gbian-emb-ticket@sunskills
```

For a local checkout, use `/plugin marketplace add ./sunskills` instead. Run `/plugin marketplace update sunskills` to pull new versions.

## Plugins

### emb-plugins

| Plugin | Owner | Contents |
|---|---|---|
| `gbian-local-debug` | [gregorybian](https://github.com/gregorybian) | `local-debug` skill: J-Link/GDB bench debugging on the STM32 boards |
| `gbian-emb-ticket` | [gregorybian](https://github.com/gregorybian) | `emb-ticket` skill: create EMB tickets on the Monday board (needs `MONDAY_TOKEN`) |

## Teams

Each team keeps its plugins in its own top-level folder: `emb-plugins/` for embedded, and e.g.
`mech-plugins/` or `strat-plugins/` for other teams. All of them are listed in the single
`.claude-plugin/marketplace.json`, so one `/plugin marketplace add` gives access to every team's plugins.
To add a team, create `<team>-plugins/` and add its plugins to `marketplace.json` with
`"source": "./<team>-plugins/<plugin>"`.

## Naming and ownership

Every plugin is named `<prefix>-<name>`, where the prefix is a short handle for the developer
(e.g. `gbian-`). The developer's GitHub username goes in `author.name` (with `author.url`
pointing at their GitHub profile) in both the plugin's `plugin.json` and its
`.claude-plugin/marketplace.json` entry, so it's clear who to ask about a plugin.

## Layout

```
.claude-plugin/marketplace.json     lists every plugin in this repo
<team>-plugins/<plugin>/            one folder per team, e.g. emb-plugins/
  .claude-plugin/plugin.json        name, description, version
  skills/<skill>/SKILL.md           model-invoked skills (+ scripts/, references/)
  commands/<name>.md                optional slash commands
  agents/<name>.md                  optional subagents
  hooks/hooks.json                  optional hooks
```

## Adding a skill

1. Put it in `<team>-plugins/<plugin>/skills/<skill-name>/SKILL.md` with `name` and `description` frontmatter.
   The description decides when Claude loads it, so say what it does *and* when to use it.
2. Refer to bundled files relative to the skill's base directory, not `~/.claude/...`.
3. For a new plugin, create `<team>-plugins/<prefix>-<name>/.claude-plugin/plugin.json` and add an entry
   in `.claude-plugin/marketplace.json`, with your GitHub username as `author` in both (see above).
4. Bump `version` in `plugin.json` so installed copies pick up the change.
5. Check it with `claude plugin validate .`
