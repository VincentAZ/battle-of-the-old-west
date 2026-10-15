# Playing Battle of the Old West

This Linux development build lets you command a frontier outfit against the AI
or another player. Each side has its own private hand.

## Readiness at a glance

The small symbol beside a battlefield name shows its readiness: a **green check**
means ready, an **amber hourglass** means recovering (newly deployed or normally
patched up), and a **pink dash** means spent or otherwise not ready. Hover or inspect
the card for the written state. Burned-out holdings and Trouble have no readiness symbol.
Wounded crew kneel and damaged holdings burn; restoration removes these effects.
The orange damaged label remains separate: a damaged holding can still
show a green check. Ready describes the card's state; whiskey and printed ability
requirements must also be satisfied before activation.

Formation slots use equal widths and heights for crew, holdings, burned-out holdings and open
spaces. Portraits and status text stay aligned across all three columns on both
player tabs. Hover or select a card to read any shortened name or status.

## Placement and damaged holdings

You choose front or back when a new crew member enters a column. A lone crew member slides back toward its holding automatically. Swapping deployed crew needs an effect such as Box Canyon or Roundup Corral; there is no free rearrange action.

A damaged, faceup holding can use its ability when ready. Select it in YOUR formation or click its model. The Battle Panel shows its action, or a reason it is unavailable: insufficient whiskey, already used, or a printed requirement. Army Fort must be undamaged to fire. Restoring a holding does not give it another use after it has already acted. Damage and readiness are shown separately.

Full-board replacement labels name the lane, front/behind position and crew member destroyed. Choose deliberately: replacing a crew member does not grant their hock effect. The battlefield labels stay compact as you zoom; hover for the full card information.

## Play directly from the battlefield

Every gameplay command has a right-click entry and a drag alternative; the
lists below cover them, including required choices and the Inspect exception.

Matches start with **Battle Plan hidden**. Your hand appears behind your holdings:
crew are actual people, and Trouble cards are a separate group of props. Your
opponent sees only question-mark placeholders for your hand. Right-click a
crew member, holding, Trouble or name label for its legal moves, or drag it to a lit target.

The foreground **Supply**, **Hip Flask**, **Pass Turn**, **Hock** and
**Ledger** props provide the corresponding right-click and drag actions.
Drag a hand model to Hock to hock it. For a required choice, right-click the
target or drag Ledger to the labelled option. Costs and destinations still
come from the game's legal moves. The **Battle Plan** button opens the optional
detailed card panel.

Your stats are on the left and the opponent's are on the right. Each header
hides or shows its stats; turn history has a separate toggle and shows the
latest two turns per player when opened. History starts collapsed; the compact
opponent play-by-play stays visible above it. In solo games, **Enemy Speed** changes the delay between
AI decisions (0.25× to 2×, initially 0.5×) and remembers your selection. Actions
finish their animations before the AI continues. Notifications have a Dismiss
button. There is no committed-move undo. Invalid drops cancel; shared destinations open
a choice menu, and destructive replacements or sacrifices ask for confirmation.


- **Right-click a card or model** for its legal actions. Right-click empty
  battlefield space for all actions, including drawing, ending your turn,
  and choosing effects that do not target a card.
- **Drag a drifter-producing holding to a lit lane space** to activate it and place
  the drifter. You can also drop onto a highlighted Battle Plan formation slot.
- **Drag Cattle Ranch or another spook-the-herd source to the lit Trouble destination.** The queued
  Stampede can be dragged too, provided a spook-the-herd ability is available. The label
  names the source and cost. **Right-click Stampede** to also choose a hand card
  with **Hock · spook the herd**, such as Vigilante or Bounty Hunter, and advance the herd for zero
  whiskey by discarding that card. The spook-the-herd hock also appears among Stampede drag choices.
- **Drag a played crew member onto Railroad Work Camp**, either its model or panel card, to
  sacrifice that crew member. Then **left-click the card to patch up**. Other holdings
  whose ability starts with a sacrifice accept the same crew member-to-holding gesture.
- **Drag a crew member to a new space** when Roundup Corral's move ability or a
  pending movement choice permits it. Movement still needs a legal effect.

Starting a drag spends nothing. Release on a highlighted destination to commit;
release elsewhere or press **Escape** to cancel. Hold near the top or bottom
of the Battle Plan scroll area to scroll while dragging. If the game changes during the
drag, start again. Labels distinguish alternate ability sources and replacement
victims. Any remaining choices in a multi-step ability stay open. Right-drag
continues to orbit the camera; middle-drag or Shift+right-drag pans.

## Drifter yard

Each side has its own fenced Drifter Pen. Six animated drifters live in each pen. When an
ability or hock effect reaches **Place a drifter**, the gate opens and one drifter
steps out for each remaining placement. **Drag an actual waiting drifter**, or its
**DRAG DRIFTER** label, onto a lit lane position. The crew member follows your pointer;
releasing on a legal destination places one drifter. Hidden card identities remain
hidden. The yard residents themselves are scenery until a legal placement exists.

Escape or an invalid drop sends the recruit back without spending the choice;
a recruit comes out again if that placement remains available. Choose **Skip**
from the right-click menu or Ledger choices to decline a placement. Unused recruits return to the yard
and the gate closes. Battle Plan is optional throughout.

## Wanted Poster Board and drifters

With a surviving Wanted Poster Board, hover over your drifters to inspect their private faces,
or select a **Drifter · inspect** card to open its details. During your Actions,
select the drifter or Wanted Poster Board and choose **Flip [crew member]** in **Your Actions**.
Affordable flips also appear in **All Actions**. The button pays the displayed
whiskey cost and turns the crew member faceup in the same space, ready, applying its
entry effects. Trouble cards stay face-down drifters. Unavailable flips explain the restriction.
Your opponent sees only a drifter until you flip it; new drifters from a single effect
become inspectable after all its placements are complete.

## Play against the AI

1. Open `launch_battle_of_the_old_west.sh` in the game folder.
2. Choose **Base Game** or **+ Boomtown**.
3. Choose **Easy**, **Normal**, or **Hard**, then **Play Single Player**.
4. Select three holdings in left-to-right order and choose **Ready for the Territory**.

Easy makes more forgiving decisions. Normal balances attacks, cover, and
whiskey. Hard also plans short attack sequences and holding combinations. All three
use the same rules, starting resources, and legal actions as you. The AI cannot
see your private hand or the shuffled deck. Difficulty describes the policy;
its strength against human players has not yet been calibrated.

Solo play runs offline without a second game instance or a server. The AI waits
for cinematic moves to finish before taking another action. Opening **Rules**
or **Settings** also pauses AI decisions until you close the panel. **Play Again**
starts a new match with the same difficulty and ruleset. **Leave** returns to
the menu, where you can choose a different difficulty. Leaving ends the solo
match; solo progress is not saved across restarts. Your saved multiplayer
reconnect details are preserved.

## Host a multiplayer game

1. Open `launch_battle_of_the_old_west.sh` in the extracted game folder.
2. One player chooses **Host a Match**. Enable Boomtown first if you want
   to include its holdings; leave it off for your first game.
3. The host's waiting screen lists local addresses with **Copy** buttons. Give
   the other player the address of the network both computers use. That player
   enters it in the menu and selects **Join Match**.
   The default port is `7777`, so an address can look like `192.0.2.20:7777`.
   `127.0.0.1` works only when both game instances run on the same computer.
4. Each player chooses three holdings, in left-to-right order. Read their abilities
   and starting-card values before confirming the selection.

Both computers must be able to reach the host's game port. The current build
uses a direct connection; it does not provide a matchmaking service or an
invitation code. Keep the host's game open while the match is in progress.

## Join from another computer

Both players need the same complete game build. The current package is for
Linux; a Windows package has not yet been built or tested.

On the same home network, join the host's Ethernet or Wi-Fi address with port
`7777`. On Linux, the waiting screen prefers physical network connections and
omits known container and tunnel adapters. Choose the network both computers
share; the first suggestion is not a reachability test. The host firewall must
allow the connection on **UDP 7777**.

For a friend in another household, a private Tailscale connection is the
recommended first setup. Alternatively, the host needs a reachable public
address and router forwarding for the game port. **Vercel is not needed** to
host this native Unreal match. Follow the steps in
[Remote play](REMOTE_PLAY.md), including how to choose the correct address.
Internet and actual two-computer play remain to be tested on this build.

## Read your position

The top bar shows whose turn it is and the shared deck count. The compact
**Battle Plan** has **YOUR**, **ENEMY**, and **HISTORY** tabs. The top strip keeps
your whiskey, hand count, turn and response status visible while you scroll. Each tab shows whiskey shots,
a hand strip, the actual front-to-rear order of each column, and the Trouble
countdown. Advanced holdings and Boarding House’s third crew member slot keep their actual positions. Enemy hand cards remain face down; their number is public.

Damaged holdings and crew have an orange border and **! DAMAGED** label in the
panel, plus a matching marker above them in the battlefield. Restoration removes
the marker. Burned-out holdings remain distinct from damaged, surviving cards.

**Hit does not remove cover.** A damaged crew member still guards the cards
behind it until destroyed or moved. A second hit destroys it; a Drifter is destroyed
by its first hit. Hit choices state whether the hit wounds or destroys the
selected target. Expand **WHY THESE TARGETS?** beneath the choices to see why
other cards are covered, including the names of damaged guards. Hovering a
covered holding also names its guards. Effects that ignore cover say so in
the explanation. These hints do not change which targets are legal.

Each section header folds independently: whiskey, hand, formation, each of its three
columns, Trouble, selected-card details, and actions. YOUR and ENEMY keep separate
preferences across sessions. A required response temporarily opens Actions even
if you folded it; afterwards, your preference returns. **Reset Panels** resets
these preferences along with panel size and position.

Drag the thin dotted border below an expanded section up or down to change its
height. Cards and text keep their size; scroll within the section to reveal
anything that does not fit. Double-click the border to reset its default
height. After clicking the border, use Up/Down for small adjustments (Shift for
larger steps); press Esc during a drag to cancel it. Heights are saved separately
for YOUR and ENEMY, including each column and both history sections. Required
responses have their own saved height and cannot be shrunk below a usable size.

**HISTORY** shows the current and immediately previous turn in resolution order,
including accepted actions, payments, choices, effects, queue movement, draws,
whiskey gains, and cleanup. Fold either turn to focus on the other. Whiskey changes
show both public balances. Drawn card identities and hidden drifter faces remain
private. Complete turns are retained even when the cinematic feed exceeds its
80-entry limit. History is also available on the match result screen. It follows
the current match and survives a client reconnect; leaving a solo match still
ends that match. This requested history feature retains public discards for one
previous turn, extending the printed game's restriction on reviewing earlier
turns' discards.

Hover over a holding or deployed crew member, either in the world or in the panel, for
its abilities, condition and cover. Hovering does not select the card or
spend whiskey. To disable this display, open **Settings**, turn **Card information
on hover** off, and choose **Apply**. Your preference is saved.

Select one of your own cards to see its legal actions in the same panel.
**All Actions** clears the source filter. Choosing an enemy card inspects it;
it never grants control over that card. Your action controls hide during the
opponent's turn, except when the rules require a response from you.

Drag the panel's title to move it, drag any edge or corner to resize it, and
use the minus button to collapse it. Escape cancels a resize. Its layout is saved. **Reset Panels**
restores the default layout. Hand cards wrap into additional rows. Expand HAND
or scroll inside it to see more cards. Formation cards, including burned-out holdings and
empty spaces, remain the same width and height when sections are resized.
Press **G** for an overview of both formations and their public abilities.

The moving artwork on hand cards and holding choices previews that card's scene.
Deployed crew continue their idle animations between moves. The Stampede appears
as a longhorn herd that moves along the fuse line, and spooking it still follows
the ordinary Stampede rules.

Face-down drifters stay unidentified to the opponent. An inspection specifically
granted by a holding such as Wanted Poster Board is private to its owner.

## Take your turn

Whiskey pays for most actions. Play crew to cover holdings and supply abilities,
schedule Trouble, use ready abilities, or hock cards for their hock effects. The
action section lists the choices the rules currently allow and prompts you when
an effect needs targets or discards. Read the whole prompt before choosing.

To play a hand card, **drag it onto a highlighted destination in the battlefield**.
Trouble also have a **Play** button when selected or under All Actions. Their
displayed cost includes automatic discounts: Cattlemen's Club reduces Cannonade from
four whiskey to three. Select an unavailable Trouble to see why it cannot play,
such as insufficient whiskey or an occupied Trouble position.
Crew show their legal places in the formation; Trouble show their available
queue position or **Play Now**. Release on a marker to commit the move. Release
elsewhere to cancel without spending whiskey. If the position changes during a
drag, start the drag again against the updated battlefield.

When an effect creates a drifter, drag a waiting drifter from the yard. For a crew member
movement choice, drag the crew member to a legal destination. The action-section
card tile is also available if you prefer it. A replacement marker names
the crew member it will replace. Effects that ask for a target, discard, or other
nonspatial decision still use the action section's choices.

You can take multiple legal actions in a turn. **End Turn** finishes your turn;
unspent whiskey is lost. Your ordinary objective is to destroy all three enemy
holdings. Some holdings introduce other ways to win, so inspect the enemy's position.

An exposed card is normally the front surviving card of its column. A
crew member in front of a holding can therefore buy time for that holding's abilities.
Damaged crew and holdings behave differently: consult the card inspector and
**Rules** when a decision depends on the distinction.

## Watch the action

Moves can trigger short cinematic shots. The game temporarily clears the large
panels so you can see the action. **Skip Cinematic** returns to the current
position immediately; skipping does not undo or change the move. A pending
player choice also returns the controls.

A character's fall can hold its shot briefly while the body comes to rest,
up to six seconds. It ends as soon as the fall has settled, and you can skip it
at any time.

The Prospector's or Assayer's analysis stays close to the character and sample case while you
choose a revealed card. **Inspect Board** or **Escape** lets you look around;
**Back to Samples** returns to the close view. **G** opens the public ability
overview. These view controls preserve the pending choice. Moving the camera
also releases the close view; selecting a response continues the action.

Over the central battlefield, use the **mouse wheel to zoom**, **right-drag to
orbit**, and **middle-drag to pan**. Shift+right-drag also pans. **Reset View**
returns to the default framing. Your chosen view returns after a cinematic.

Use **Camera**, or press **Tab**, to change the tactical view. **Rules** opens a
searchable offline reference during play, with expanded rules and explanations
of all 104 current cards. Press Enter to search, choose a category, and switch
between the active ruleset and all current cards. Designer clarifications and
match interpretations are listed separately.

## Adjust the picture and sound

Open **Settings** from the menu or during a match. Choose your resolution,
window mode, graphics quality, frame limit and master volume, then **Apply**.
Borderless mode uses the desktop resolution. Higher graphics presets cost
more rendering time; reduce the preset if the game runs slowly.

A resolution or window-mode change asks you to **Keep** or **Revert** it. If
you do nothing for 15 seconds, the previous settings return automatically.
Confirmed settings are remembered when you next start the game. Settings are
local to your computer and do not change the match or the other player's view.

## Finish or reconnect

After a multiplayer match, both players choose **Rematch** to start another game.
After a solo match, choose **Play Again**. **Leave**
returns to the menu; **Quit** closes the application. Leaving as the host ends
the hosted connection.

If a client loses its connection, join the same host address to reclaim its
reserved seat. The standard player profile remembers its last successful
connection privately across application restarts. A restarted host is a new
server session; this build does not save the host's match to disk.

## Build status

This is a development build. Automated same-computer multiplayer checks are
part of development; they do not establish performance or connectivity on a
second computer. See `runtime-validation.json`, when present, for the checks
completed on that exact build.

## Adjustable field information and camera

Drag the YOUR INFO or ENEMY INFO title bar to move it. Drag any edge or corner to resize it; the layout is remembered. Use the title-bar minus button to fold the panel, and Reset Panels to restore its original layout. Stats and history can also hide independently. History retains the latest two turns of each player. Older and Newer select a turn; Latest returns to the current turn and follows play. Oldest First and Newest First change entry order. Scroll the full-width list to read every entry. Text stays the same size when the panel is resized.

Use the top camera buttons for zoom, pan, rotation and tilt. Mouse wheel zooms; right-drag rotates; middle-drag or Shift-right-drag pans. Hold Ctrl while right-dragging or middle-dragging to move vertically (drag up to rise, down to descend), or use HEIGHT + / −. Horizontal panning, vertical movement and tilt allow full three-axis positioning, including floor-level views and looking upward. Manual movement can pass through scenery. Zoom reaches close inspection and a distant overview. Reset View returns to the default view.

Pawn Shop must be activated before choosing its two discards. Cards hocked earlier in the turn do not count. After activating, use the Ledger choices to discard two cards still in hand, optionally resolve their hock effects, then choose an exposed enemy to hit.


## Dragging actions and finishing choices

Drag a holding or crew member to a labelled action or target to initiate its ability.
If the ability asks for another choice, drag that same source again to the next
labelled target. You can also use the Ledger for pending choices.
The whiskey prop and your WHISKEY readout can be dragged to initiate legal paid
actions, and to complete pending choices. Whiskey is spent only when the legal
action is committed, not when you pick up the drag. Right-click offers the same
actions. Escape cancels a drag before commitment.

Boarding House's one-whiskey ability removes either player's burned-out holding, then asks
for an exposed enemy card to hit. Drag Boarding House to start, drag it to
the burned-out holding, then drag it again to the hit target. Removing a burned-out
holding does not replace the hit step. Its separate two-whiskey ability performs a spook the herd.

### Whiskey and Supply

Drag from the single **Whiskey** source to a highlighted physical destination.
The destination shows the actual cost: Supply draws for two whiskey; Hip Flask
stores one. Multiple legal actions at the same destination open a choice menu.
Picking up whiskey or cancelling a drop spends nothing. A changed battlefield
invalidates the drag or confirmation.

A hand card with the **draw** hock effect can also be dropped directly onto
**Supply**. This hocks that card and draws according to its printed effect;
it does not pay for a normal two-whiskey draw. Other hock effects use **Hock**.

### Card details and Ledger

Click a card or holding to read its details in the bottom panel. Clicking another
card switches the details; clicking empty battlefield closes them. Required
target choices take priority over inspection. Hover gives a short state summary.
The collapsible **Abilities in Play** side reference lists public abilities and
readiness without exposing enemy hands or private drifter faces.

Left-click **Ledger** to open its dedicated war room. It lists current
legal actions by source, with costs and subsequent choices handled by the rules.
Escape or a click outside closes it. Right-click continues to offer contextual
actions, and Battle Plan remains available independently.

The gold **Next Action** strip stays separate from history and details. During
close-ups, ordinary overlays hide while a caption identifies the card and action.
Trouble plays highlight their queue or Play Now destination.

### Battlefield text

Use **TEXT: ON / OFF** at the left of the camera toolbar to toggle all battlefield
text: card and utility names, conditions, area signs, lane numbers, hidden-hand
question marks, hover descriptions, and drag captions. Objects remain selectable
and drop-target rings remain visible. Toggle text back on to distinguish actions
that share the same target. Info panels and menus remain available.
