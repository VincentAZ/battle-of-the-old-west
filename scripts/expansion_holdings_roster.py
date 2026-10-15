"""Western presentation for the 32 verified Boomtown holdings.

Names follow Feedback/WESTERN_REBRAND.md and the existing Western vocabulary.
Rationales describe the actual local catalog; old speculative ability summaries
are not sources for either rules or history. The six formerly unidentified
cards are identified in game/data/boomtown.verified.json.
"""

# Same tuple contract as holdings_roster.HOLDINGS. Distinct slugs preserve every
# base holding's approved/review source and imported asset name.
HOLDINGS = {
    'gunsmith': ('gunsmith', 'Gunsmith', 'Town', 5.5, 'Equips drifters with a paid hit ability and recruits another.'),
    'jailhouse': ('jailhouse', 'Jailhouse', 'Town', 5.5, 'Takes a wounded enemy into the outfit; separately patches another friendly card.'),
    'robbers_roost': ('robbers-roost', 'Robbers Roost', 'Mountains', 5.5, 'The outlaw hideout profits whenever its Stampede resolves.'),
    'timber_ram': ('timber-ram', 'Timber Ram', 'Timber', 6.0, 'Needs six crew to destroy an enemy holding; historical form still requires evidence.'),
    'smuggler_s_landing': ('smugglers-landing', "Smuggler's Landing", 'River', 6.0, 'Hocks the effect of newly arrived crew while keeping them in play.'),
    'rockslide_ridge': ('rockslide-ridge', 'Rockslide Ridge', 'Mountains', 6.0, 'Destroys crew in a column and hits its holding, then destroys itself.'),
    'bounty_office': ('bounty-office', 'Bounty Office', 'Town', 4.5, 'Hits a holding when the enemy has no drifters; the enemy may then hire one.'),
    'packer_s_cabin': ('packers-cabin', "Packer's Cabin", 'Mountains', 4.5, 'Hits an undamaged friendly card to patch up another. Packer association is flavour, not an ability claim.'),
    'revival_tent': ('revival-tent', 'Revival Tent', 'Range', 5.5, 'Sacrifices one of the outfit to hit an exposed enemy.'),
    'vigilance_committee': ('vigilance-committee', 'Vigilance Committee', 'Town', 5.5, 'Spends five cards and whiskey to destroy any enemy crew or holding.'),
    'courthouse': ('courthouse', 'Courthouse', 'Town', 6.0, 'Spooks the herd; when its Stampede resolves, delays the opposing Trouble.'),
    'post_office': ('post-office', 'Post Office', 'Town', 4.5, 'Pays for two cards: incoming correspondence supplies new options.'),
    'army_surgeon_s_tent': ('army-surgeons-tent', "Army Surgeon's Tent", 'Range', 5.0, 'Moves wounded crew into its column and patches them up; can also spook the herd.'),
    'wagon_fort': ('wagon-fort', 'Wagon Fort', 'Range', 6.5, 'Starts forward with room behind it and recruits up to three drifters. It does not move like Riverboat.'),
    'free_homestead': ('free-homestead', 'Free Homestead', 'Range', 5.0, 'Recruits a drifter when an enemy holding is exposed.'),
    'coal_yard': ('coal-yard', 'Coal Yard', 'Rail', 5.5, 'Spooks the herd; a newly launched Stampede starts at three.'),
    'gallows': ('gallows', 'Gallows', 'Town', 5.0, 'Destroys an exposed enemy, whose controller may use its ability once without whiskey.'),
    'pawn_shop': ('pawn-shop', 'Pawn Shop', 'Town', 5.0, 'Discards two cards, optionally hocks both, then hits an exposed enemy.'),
    'nitro_works': ('nitro-works', 'Nitro Works', 'Mountains', 5.5, 'Destroys all friendly crew in its column to hit an exposed enemy.'),
    'crimp_house': ('crimp-house', 'Crimp House', 'River', 5.5, 'Patches a crew member, then the top three cards can replace them with a drifter and grant a round.'),
    'wanted_poster_board': ('wanted-poster-board', 'Wanted Poster Board', 'Town', 4.5, 'Inspects drifters and reveals crew by paying their cost; they enter ready.'),
    'boot_hill': ('boot-hill', 'Boot Hill', 'Town', 5.5, 'Patches another friendly card after a friendly card was hit or destroyed this turn.'),
    'boarding_house': ('boarding-house', 'Boarding House', 'Town', 6.0, 'Removes a burned-out holding to make room for crew and hits an exposed enemy; also spooks the herd.'),
    'rustlers_corral': ('rustlers-corral', "Rustlers' Corral", 'Range', 6.0, 'With a drifter present, recruits another or spooks the herd.'),
    'quaker_settlement': ('quaker-settlement', 'Quaker Settlement', 'Range', 5.5, 'Patches another friendly card while undamaged, but hits an exposed enemy while damaged.'),
    'chuckwagon': ('chuckwagon', 'Chuckwagon', 'Range', 5.0, 'Readies other holdings and all undamaged crew.'),
    'horse_trader': ('horse-trader', 'Horse Trader', 'Range', 5.5, 'Trades three cards for two at no whiskey cost.'),
    'pony_express_station': ('pony-express-station', 'Pony Express Station', 'Range', 5.5, 'Returns crew to hand; that person and its other copy cannot enter again this turn.'),
    'lookout_ridge': ('lookout-ridge', 'Lookout Ridge', 'Mountains', 6.0, 'Exposes battlefield cards on both sides for the rest of the turn.'),
    'dance_hall': ('dance-hall', 'Dance Hall', 'Town', 5.5, 'A fight hits an exposed enemy, then the opponent wounds one of your exposed crew.'),
    'apothecary': ('apothecary', 'Apothecary', 'Town', 4.5, 'Discards the top card and optionally uses its hock effect; it does not inherently patch up.'),
    'cattlemen_s_club': ('cattlemens-club', "Cattlemen's Club", 'Town', 5.5, 'Reduces Trouble play costs and separately spooks the herd; it does not reduce all ability costs.'),
}

PROVISIONAL_NAMES = {'vigilance_committee', 'post_office', 'nitro_works', 'rustlers_corral', 'horse_trader', 'lookout_ridge'}
# Names remain intact while the historical/ability fit is reviewed. A flag is
# not approval, and does not permit inventing history to justify the theme.
MAPPING_REVIEW = {
    'timber_ram': 'A timber battering ram needs a documented Western example before depiction.',
    'packer_s_cabin': 'Do not invent a surviving Packer cabin or imply the ability depicts the historical incident.',
    'quaker_settlement': 'A retaliatory attack conflicts with the pacifist rationale; do not portray Quakers as armed combatants.',
    'pony_express_station': 'Pony Express operated in 1860-1861. Depict a documented station reused during 1865-1900, not an active later Express.',
}
