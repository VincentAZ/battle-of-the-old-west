# Playing Battle of the Old West with a remote friend

You do not need Vercel. Battle of the Old West is a native Unreal game: one player's game
hosts the match, and the other player's game connects to it. Keep the host's
game open for the whole match.

Both players need the **same game build**, including its packaged assets and
card data. Send the complete extracted game folder, not just the executable.
The current package is for Linux. A Windows package has not yet been built or
tested; installing Tailscale on Windows does not make the Linux game run there.

## If you are on the same home network

1. Connect both computers to the same home network. Guest Wi-Fi can isolate
   devices even when the network name looks similar.
2. The host opens the game and chooses **Host a Match**. Choose the ruleset
   before hosting.
3. On the waiting screen, copy the address for the host's Ethernet or Wi-Fi
   connection. The development computer was last checked at
   `192.0.2.16:7777`; confirm the current address after a restart or network
   change.
4. The guest enters that address in **Join Match**. Both players choose three
   holdings and confirm them.

The suggested IPv4 list prefers physical Ethernet/Wi-Fi interfaces on Linux
and omits known container and tunnel interfaces, loopback, link-local and
inactive links. It does not reject an address merely because it starts
with `172.`; a real home or office network can use that range. Windows uses
Unreal's existing active Ethernet/Wi-Fi enumeration, which can still include
virtual Ethernet adapters. Unknown interface names or unavailable metadata
can also leave extra suggestions. Choose the connection both computers
actually share; appearing first does not prove the guest can reach it.

Manual joining is independent of these suggestions. You can enter the
host's IPv4 address or DNS name followed by `:7777`. For an IPv6 address
with an explicit port, use square brackets: `[2001:db8::10]:7777` is a
documentation example, not an address to join. Scoped link-local syntax
such as `%eth0` is not accepted by the current join field. IPv6 routing,
listener and firewall reachability still need testing on the actual pair
of computers; the game does not add IPv6 suggestions in this change.
`127.0.0.1:7777` reaches another game on your own computer only.

The host's firewall must permit the guest's connection to **UDP port 7777**.
If a different game port was selected at launch, use that port in both the
firewall rule and join address. The game uses Unreal's direct IP networking;
[Epic's server guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-dedicated-servers-in-unreal-engine)
documents the default port and the `-port` launch option.

## If your friend is in another household

For an initial playtest, I recommend a private Tailscale connection. It gives
the guest a way to reach your computer over the Internet and usually works
without router port forwarding. Connections can use a relay when a direct
path is unavailable. [Tailscale firewall and connectivity documentation](https://tailscale.com/docs/integrations/firewalls).

1. Both players install Tailscale and sign in on the computers running the
   game. Each can use their own account. Follow the
   [official quickstart](https://tailscale.com/docs/how-to/quickstart).
2. In the host's Tailscale admin console, open **Machines**, find the game
   computer, and choose **Share**. Create a single-use share link and give it
   privately to your friend. They accept it with their Tailscale account.
   Both sharing and accepting a shared machine require an Owner, Admin, or
   IT admin role in the respective account. If either account is managed by
   an organization, its administrator may need to handle this step.
   [Tailscale sharing requirements](https://tailscale.com/docs/features/sharing).
3. The guest finds the shared host in their own Tailscale app or
   `tailscale status` output. Use the host's IPv4 address **as shown to the
   guest**; shared-device addresses can differ between accounts. The full
   `computer.network.ts.net` name is another option when MagicDNS is enabled.
   [Tailscale machine sharing](https://tailscale.com/docs/features/sharing).
4. The host chooses **Host a Match** in Battle of the Old West. The guest enters the shared
   host's address followed by `:7777`, then chooses **Join Match**. A Tailscale
   address commonly starts with `100.`; use the actual address, not this
   description as an example to copy.
5. If custom Tailscale access rules or the host firewall block the connection,
   allow the guest to reach this host on UDP 7777. Sharing can expose other
   services on that computer too; its access policy can restrict the guest to
   the game port. [Sharing access controls](https://tailscale.com/docs/features/sharing#sharing-and-access-control-policies).

This is a proposed connection setup. This Battle of the Old West build has not yet completed
a playtest between two physical computers over Tailscale or the public
Internet.

## Direct Internet connection without Tailscale

If your router has a reachable public IPv4 address:

1. Keep the host's local address stable with a router DHCP reservation.
2. In the router, forward external **UDP 7777** to **UDP 7777** at the host's
   current local IP address. Permit that game traffic through the host firewall.
3. Start **Host a Match**. Give the guest the router's current **public** IPv4
   address followed by `:7777`. An address beginning `192.168.` is local to
   your home and cannot be used by an ordinary Internet client.
4. Have the friend join from their own network. Testing the public address
   from inside the host's home depends on the router's loopback support.

Carrier-grade NAT (CGNAT) can prevent inbound connections even with a correct
home-router forwarding rule. Ask your ISP whether it provides a reachable
public IPv4 address, or use the private connection above. An ISP's
[CGNAT explanation](https://articles.spintel.net.au/pdf-1002.html) describes
why ordinary port forwarding can fail behind its shared public address.

## What Vercel would do

A future website, account service, or lobby API could use Vercel. The current
Unreal match needs a running native game process with a reachable UDP socket.
Deploying a website does not supply that connection. An always-available
service would require a deployed dedicated game server plus the client work
to discover and join it.

This is an architectural distinction: Vercel supports web applications and
functions, including its newer WebSocket beta, but this game does not use a
WebSocket transport. [Vercel Functions](https://vercel.com/docs/functions),
[WebSocket support](https://vercel.com/changelog/websocket-support-is-now-in-public-beta).

An in-game friends list, invitation codes, matchmaking, and automatic game
relay integration are still unimplemented.

## If joining fails

Check the build matches, the host is actually on its waiting or match screen,
the address belongs to the host on the chosen connection, and the port is
correct. For Tailscale, check that both clients are connected and the share
was accepted. For direct Internet play, check the router forwarding target
and whether the ISP uses CGNAT. Opening the address in a web browser does not
test this UDP game service.

After a dropped connection, join the same host address to reclaim your seat.
If the host closed or restarted the game, the old match is gone; this build
does not save a hosted match to disk. See [the player guide](PLAYER_GUIDE.md)
for gameplay and reconnect behavior.
