#pragma once
#include "OldWestCosmetics.h"
#include "OldWestHoldingsCatalog.h"
#include "OldWestExpansionHoldings.h"
#include "OldWestTroubleCatalog.h"
#include <string_view>

// Presentation text only. Keys describe the displayed asset, not a new card ID.
// Add a note with each Western asset; never use a hidden/private face to pick one.
namespace OldWestAssetHistory
{
struct FNote
{
    const char* Key;
    const char* Title;
    const char* Body;
    const char* Source;
    const char* Url;
    const char* Attribution = nullptr;
    const char* RelatedKey = nullptr;
};
inline constexpr FNote Notes[] = {
    {"holding-rustlers-corral",
     "Rustlers' Corral",
     "Open-range ranchers gathered cattle for branding and shipment.\nRustlers stole livestock from these widely scattered herds.\nThis fictional enclosure uses documented pole-corral construction.",
     "Theodore Roosevelt, Ranch Life and the Hunting-Trail (New York: Century Co., 1888), full OCR text, Internet Archive (New York Public Library copy)",
     "https://archive.org/stream/ranchlifehunting00roos/ranchlifehunting00roos_djvu.txt",
     "Fictional architectural composite; dimensions and exact colours reconstructed. Fire damage is a game state. Sources: https://archive.org/stream/ranchlifehunting00roos/ranchlifehunting00roos_djvu.txt https://npgallery.nps.gov/NRHP/GetAsset/NRHP/92000836_text https://www.wyohistory.org/encyclopedia/roundups-wyomings-open-range https://npgallery.nps.gov/NRHP/GetAsset/bc356345-c429-45ff-91aa-7507e8de9aa9 https://research.fs.usda.gov/download/treesearch/37440.pdf https://www.nps.gov/grko/learn/historyculture/openrange.htm"},
    {"holding-quaker-settlement",
     "Quaker Settlement",
     "Quaker settlers built a West Branch meetinghouse in 1857.\nFriends emphasized simplicity, equality, service and peace.\nThis fictional settlement uses a plain meetinghouse as its landmark.",
     "NPS, Worshipping with the Friends",
     "https://www.nps.gov/media/video/view.htm?id=801FEB07-1946-4B47-90DD-29ADE00FD968",
     "Fictional architectural composite; dimensions and exact colours reconstructed. Fire damage is a game state. Quaker peace testimony is distinct from the unchanged card ability. Sources: https://www.nps.gov/media/video/view.htm?id=801FEB07-1946-4B47-90DD-29ADE00FD968 https://home.nps.gov/articles/west-branch-quaker-heritage.htm"},
    {"holding-dance-hall",
     "Dance Hall",
     "Dance halls and saloons served Kansas cattle towns.\nTheir painted storefronts advertised entertainment to passing customers.\nThis hall is a fictional reconstruction of that commercial building type.",
     "Cowtowns - Kansapedia - Kansas Historical Society",
     "https://www.kansashistory.gov/p/cowtowns/15598",
     "Fictional architectural composite; dimensions and exact colours reconstructed. Fire damage is a game state. Sources: https://www.kansashistory.gov/p/cowtowns/15598 https://www.nps.gov/klgo/learn/historyculture/mascot.htm https://www.onlinenevada.org/havens-heartless-world-part-i-virginia-citys-saloons-and-archaeology-wild-west https://www.nps.gov/orgs/1739/upload/preservation-brief-11-storefronts.pdf https://www.loc.gov/resource/sn84029838/1877-05-12/ed-1/?sp=4 https://www.loc.gov/resource/sn84027670/1881-05-12/ed-1/?sp=3 https://www.loc.gov/item/2005684542/ https://archive.org/download/sherwin-williams-company-1884/Sherwin-Williams%20Company%2C%201884_djvu.txt https://soilseries.sc.egov.usda.gov/OSD_Docs/S/SPEARVILLE.html https://www.loc.gov/resource/sn84029838/1877-07-21/ed-1/?sp=4"},
    {"holding-apothecary",
     "Apothecary",
     "Drugstores sold medicines and other goods in Western towns.\nColoured show globes advertised the pharmacy trade.\nThis shop is a fictional, period-informed reconstruction.",
     "Fort Lewis College Center of Southwest Studies: Peacock store and stagecoach, Durango, 1881–1882; SWP 001 I-02-07",
     "https://www.fortlewis.edu/finding_aids/images/P001/P00110207.htm",
     "Fictional game damage; reconstructed dimensions. Sources: https://www.fortlewis.edu/finding_aids/images/P001/P00110207.htm https://waring.library.musc.edu/exhibits/ShowGlobes/Definition.php https://pharmacy.wisc.edu/wp-content/uploads/2016/04/AC3.pdf https://www.nps.gov/orgs/1739/upload/preservation-brief-10-paint-problems-exterior-woodwork.pdf https://www.nps.gov/orgs/1739/upload/preservation-brief-19-wood-shingle-roofs.pdf https://waring.library.musc.edu/exhibits/ShowGlobes/History.php"},
    {"holding-boarding-house",
     "Boarding House",
     "Boarding houses provided lodgings in Western towns.\nA Denver photograph records a timber boarding house with porches and tall windows.\nThis fictional building uses documented period forms and colours.",
     "Mrs. Power’s boarding house, Denver Public Library X-23881",
     "https://digital.denverlibrary.org/nodes/view/1044532",
     "Fictional game damage; reconstructed dimensions. Sources: https://digital.denverlibrary.org/nodes/view/1044532 https://www.nps.gov/articles/italianate-style-architecture.htm https://history.denverlibrary.org/neighborhood-history-guide/curtis-park-denvers-first-streetcar-suburb https://www.nps.gov/articles/why-is-white-haven-painted-green.htm https://www.nps.gov/orgs/1739/upload/preservation-brief-19-wood-shingle-roofs.pdf"},
    {"holding-boot-hill",
     "Boot Hill",
     "Cowtown cemeteries served frontier communities.\nOgallala graves often had wooden headboards.\nThis prairie cemetery is a fictional composite.",
     "Nebraska State Historical Society, Marker Monday: Boot Hill",
     "https://history.nebraska.gov/marker-monday-boot-hill/",
     "Fictional game damage; reconstructed dimensions. Sources: https://history.nebraska.gov/marker-monday-boot-hill/ https://assets.simpleviewinc.com/simpleview/image/upload/v1/clients/keithcountyne/Boot_Hill_Walking_Tour_39c8fe84-0207-4830-ad8b-23ddf604beb4.pdf https://soilseries.sc.egov.usda.gov/OSD_Docs/K/Keith.html https://byf.unl.edu/buffalo-grass/ https://www.loc.gov/pictures/item/2021758034/"},
    {"holding-cattlemens-club",
     "Cattlemen's Club",
     "Cheyenne cattlemen founded an exclusive social club in 1880.\nIts clubhouse offered dining, reading and lodging beneath a mansard roof.\nThis fictional holding adapts documented 1880s forms; its exact colours are reconstructed.",
     "UW American Heritage Center, Luxury on the High Plains: Benjamin F. Davis Papers",
     "https://www.wyomingpublicmedia.org/show/archives-on-the-air/2024-12-12/luxury-on-the-high-plains-448-benjamin-f-davis-papers",
     "Fictional game damage; reconstructed dimensions. Sources: https://www.wyomingpublicmedia.org/show/archives-on-the-air/2024-12-12/luxury-on-the-high-plains-448-benjamin-f-davis-papers https://npgallery.nps.gov/GetAsset/fff6fa51-1888-401d-adec-930eaaab98f4/ https://www.phmc.state.pa.us/portal/communities/architecture/styles/second-empire.html https://www.nps.gov/orgs/1739/upload/preservation-brief-29-slate-roofs.pdf https://www.nps.gov/orgs/1739/upload/preservation-brief-28-painting-interiors.pdf https://www.wyohistory.org/encyclopedia/wyoming-cattle-boom-1868-1886"},
    {"holding-coal-yard",
     "Coal Yard",
     "Rail sidings served Denver's coal yards.\nStorage sheds supplied retail coal customers.\nThis yard is a fictional 1880s composite.",
     "Sanborn Map Company, Denver, 1887, sheet 36",
     "https://www.loc.gov/item/sanborn00985_001/",
     "Fictional game damage; reconstructed dimensions. Sources: https://www.loc.gov/item/sanborn00985_001/ https://www.nps.gov/goga/learn/historyculture/upload/2006-fopo-hsr.pdf https://npgallery.nps.gov/GetAsset/1d25f844-260e-41d1-afba-ed247519a9ef https://fraser.stlouisfed.org/title/commercial-financial-chronicle-1339/december-28-1889-529554/fulltext https://images.nypl.org/index.php?id=G90F028_066ZF&t=w"},
    {"holding-crimp-house",
     "Crimp House",
     "Crimps recruited sailors through debt and, sometimes, coercion in western ports.\nPortland lodging houses and saloons could be part of this exploitative trade.\nThis fictional waterfront house uses a period brick-and-cast-iron building type.",
     "Richard Engeman, Shanghaiing in Portland and the Shanghai Tunnels Myth",
     "https://www.oregonencyclopedia.org/articles/shanghai_tunnels_myth/",
     "Fictional game damage; reconstructed dimensions. Sources: https://www.oregonencyclopedia.org/articles/shanghai_tunnels_myth/ https://www.oregonencyclopedia.org/articles/portland_seamen_s_friend_society/ https://www.oregonencyclopedia.org/media/uploads/47424.jpg https://heritagedata.prd.state.or.us/historic/index.cfm?do=main.loadFile&load=NR_Noms%2F74001706.pdf https://home.nps.gov/orgs/1739/upload/preservation-brief-27-cast-iron.pdf https://www.nps.gov/orgs/1739/upload/book-metals-in-america-part-4.pdf https://www.nps.gov/orgs/1739/upload/preservation-brief-04-roofing.pdf"},
    {"holding-horse-trader",
     "Horse Trader",
     "Montana ranches bred and sold working and riding horses.\nGrant-Kohrs used small log stallion barns with haylofts and separate feeding spaces.\nThis fictional sale yard draws on those documented buildings.",
     "NPS, Grant-Kohrs Ranch National Historic Landmark Nomination (2001)",
     "https://npgallery.nps.gov/NRHP/GetAsset/bc356345-c429-45ff-91aa-7507e8de9aa9",
     "Fictional game damage; reconstructed dimensions. Sources: https://npgallery.nps.gov/NRHP/GetAsset/bc356345-c429-45ff-91aa-7507e8de9aa9 https://npshistory.com/publications/grko/habs-mt-39-h.pdf https://research.fs.usda.gov/download/treesearch/37430.pdf https://www.nps.gov/articles/000/grant-kohrs-landscape-ranching-history.htm"},
    {"holding-nitro-works",
     "Nitro Works",
     "California Powder Works supplied western mining and construction from the 1860s.\nIts Santa Cruz works added smokeless-powder production in the mid-1890s.\nThis fictional works combines period industrial exteriors with a documented yellow office.",
     "Barry Brown, The California Powder Works and San Lorenzo Paper Mill (2008), SCPL AR-071; PDF pages 3–4, 12–13, 23, 29, 31",
     "https://history.santacruzpl.org/omeka/items/show/134535",
     "Fictional game damage; reconstructed dimensions. Sources: https://history.santacruzpl.org/omeka/items/show/134535 https://npgallery.nps.gov/GetAsset/76872f52-29ef-4b2a-9fb4-48beed1c2d85 https://www.nps.gov/orgs/1739/upload/preservation-brief-04-roofing.pdf https://research.fs.usda.gov/download/treesearch/32202.pdf"},
    {"holding-packers-cabin",
     "Packer's Cabin",
     "Alfred Packer guided prospectors on the ill-fated 1873–74 expedition to Colorado.\nThis fictional shelter follows a separate 1874 Mancos Valley cabin photograph.\nIt is not an authenticated Packer residence or a depiction of the expedition.",
     "William Henry Jackson, No. 233, Settlers’ Cabin in the Rio de las Mancos, Expedition of 1874; Utah State University P0349 2:02:01",
     "https://exhibits.usu.edu/items/show/15207",
     "Fictional game damage; reconstructed dimensions. Sources: https://exhibits.usu.edu/items/show/15207 https://www.nps.gov/orgs/1739/upload/preservation-brief-26-log-buildings.pdf https://research.fs.usda.gov/download/treesearch/32194.pdf https://www.nps.gov/meve/learn/nature/geology.htm https://www.museum.littletonco.gov/Research/Littleton-History/Biographies/Packer https://research.fs.usda.gov/silvics/ponderosa-pine"},
    {"holding-pawn-shop",
     "Pawn Shop",
     "Denver archive records cite pawn-and-jewelry advertising in 1872.\nThree gilded balls served as a pawnbroker’s trade emblem.\nThis fictional shop combines documented period storefront forms and materials.",
     "DPL, Gottheimer, Davidson and company",
     "https://digital.denverlibrary.org/nodes/view/1365077",
     "Fictional game damage; reconstructed dimensions. Sources: https://digital.denverlibrary.org/nodes/view/1365077 https://history.denverlibrary.org/neighborhood-history-guide/lodo-denvers-lower-downtown-success-story https://www.nps.gov/orgs/1739/upload/preservation-brief-11-storefronts.pdf https://www.historicnewengland.org/explore/collections-access/gusn/371727 https://www.nps.gov/orgs/1739/upload/preservation-brief-25-signs.pdf https://www.nps.gov/orgs/1739/upload/preservation-brief-04-roofing.pdf https://www.nps.gov/articles/why-is-white-haven-painted-green.htm"},
    {"holding-revival-tent",
     "Revival Tent",
     "California camp meetings used large canvas shelters in the nineteenth century.\nAn 1872 Windsor gathering included a circular meeting tent reported as sixty feet across.\nThis fictional miniature combines that Western precedent with period tent and seating references.",
     "Northern California Conference, California Conference History",
     "https://nccsda.com/about-us/california-conference-history/",
     "Fictional game damage; reconstructed dimensions. Sources: https://nccsda.com/about-us/california-conference-history/ https://digital.pitts.emory.edu/s/masquerade/item/13315 https://npgallery.nps.gov/GetAsset/3fe829b3-8b64-462c-8da1-fbd61f70aa36 https://mvmuseum.org/wp-content/uploads/2024/11/November-2023-Quarterly.pdf"},
    {"holding-timber-ram",
     "Timber Ram",
     "A 1904 county history recalls a tree trunk used as a ram during an 1879 Washington Territory jail rescue.\nThe account describes a handy trunk used by several rescuers.\nThis fictional pine-log reconstruction supplies no claim about the original trunk’s species or dimensions.",
     "An Illustrated History of Stevens, Ferry, Okanogan and Chelan Counties, State of Washington, Western Historical Publishing Company (1904)",
     "https://archive.org/details/illustratedhisto00spok",
     "Fictional game damage; reconstructed dimensions. Sources: https://archive.org/details/illustratedhisto00spok https://www.fs.usda.gov/pnw/pubs/pnw_gtr390.pdf https://research.fs.usda.gov/download/treesearch/32194.pdf https://research.fs.usda.gov/silvics/ponderosa-pine"},
    {"holding-vigilance-committee",
     "Vigilance Committee",
     "Montana’s vigilance committees were self-appointed groups acting outside regular government.\nThis fictional meeting hall draws on Virginia City’s 1863 Kiskadden commercial block.\nThat building’s claimed vigilante meeting connection remains a legend.",
     "Montana Heritage Commission, structural repair report (2013), Kiskadden Barn, PDF page 33",
     "https://archive.legmt.gov/content/Committees/Interim/2013-2014/EQC/Meetings/September-2013/MHC-structural-repair-report.pdf",
     "Fictional game damage; reconstructed dimensions. Sources: https://archive.legmt.gov/content/Committees/Interim/2013-2014/EQC/Meetings/September-2013/MHC-structural-repair-report.pdf https://static1.squarespace.com/static/5e7d4bd4b56fd5047d73a90b/t/63e03a52ee40ff1e12073642/1675639380556/BULLETIN%2B2022%2BSpring.pdf https://mhs.mt.gov/education/StoriesOfTheLand/Part2/Chapter6/Ch6Educators/vigilantes https://www.nps.gov/orgs/1739/upload/preservation-brief-22-stucco.pdf https://research.fs.usda.gov/download/treesearch/32194.pdf https://www.nps.gov/orgs/1739/upload/preservation-brief-19-wood-shingle-roofs.pdf"},
    {"holding-wagon-fort",
     "Wagon Fort",
     "Overland wagon trains formed temporary corrals when they camped.\nTongues and chains linked the wagons to help contain livestock.\nThis fictional holding compresses a larger encampment into eight parked wagons.",
     "BLM, National Historic Oregon Trail Interpretive Center, Wagons on the Oregon Trail",
     "https://www.blm.gov/es/sites/default/files/learn_interp_nhotic_faqwagons.pdf",
     "Fictional game damage; reconstructed dimensions. Sources: https://www.blm.gov/es/sites/default/files/learn_interp_nhotic_faqwagons.pdf https://www.nps.gov/articles/000/traveling-emigrant-trails.htm https://www.nps.gov/articles/000/wagons-on-the-trails.htm https://www.nps.gov/jeff/planyourvisit/overland-wagon.htm https://www.nps.gov/cali/planyourvisit/upload/CALI_LFT_ADA_Map-guide012813.pdf"},
    {"holding-bounty-office", "Bounty Office",
     "Fort Smith's marshal worked from former barracks.\nDeputies documented arrests and mileage for fees.\nThis office is a fictional reconstruction.",
     "National Park Service, Fort Smith history and landmark nomination",
     "https://www.nps.gov/fosm/learn/historyculture/work-of-deputy-marshals.htm",
     "Fictional detached office inspired by the 1875-1888 office use of Fort Smith's former barracks. The game title does not establish an independent historical Bounty Office. Statutory deputy fees for tasks and travel were distinct from private rewards. Five bays compress the prototype's ten; dimensions, detail and natural material hues are reconstructed. Slate is a period material analogue from the same site's commissary, not proof of the barracks roof fabric. Later 1891 additions are excluded. The collapsed condition is fictional game damage, not a documented fire. Sources: https://npshistory.com/publications/fosm/nr-fort-smith-2015.pdf https://www.nps.gov/fosm/learn/historyculture/work-of-deputy-marshals.htm https://www.nps.gov/fosm/planyourvisit/park-brochure.htm"},
    {"holding-smugglers-landing", "Smuggler's Landing",
     "Boats carried Rio Grande trade.\nAn 1879 report noted smuggling near Roma.\nThis landing is a reconstruction.",
     "U.S. diplomatic records; Library of Congress; El Paso Public Library",
     "https://history.state.gov/historicaldocuments/frus1884/d265",
     "Fictional Rio Grande landing, 1879-1885. The 1879 Almaraz report supplies smuggling context near Roma, not a dock plan. Period Brownsville and El Paso photographs support shallow craft and timber approaches; no photographed operators are identified as smugglers. Interior framing, ramp, mooring, cargo arrangement and setting are reconstructed. Closed cases use a separate 1865 Bertrand cargo-construction analogue. Modern river and botanical references support material colours and plausible narrow-leaf willow, not a surveyed historical planting. The charred hull is fictional game damage. Sources: https://www.loc.gov/pictures/item/2016646740/ https://texashistory.unt.edu/ark:/67531/metapth875255/ https://secure-sha.org/bottle/pdffiles/Bertrand_Bottles_Book.pdf https://tpwd.texas.gov/landwater/land/programs/landscape-ecology/ems/emst/woody-wetlands-and-riparian/tamaulipan-floodplain https://yavapaiplants.extension.arizona.edu/salix-exigua https://www.nps.gov/articles/southwest-river-environments.htm https://research.fs.usda.gov/download/treesearch/62268.pdf"},
    {"holding-robbers-roost", "Robbers Roost",
     "Robbers Roost sheltered outlaw gangs.\nA local cabin used upright juniper posts.\nThis hideout layout is reconstructed.",
     "Bureau of Land Management; National Park Service ranching study",
     "https://www.blm.gov/visit/robbers-roost-dirty-devil",
     "Reconstructed 1890s central Utah hideout using a documented local building method: stockade juniper-post walls and smaller roof poles covered in bark. The source describes a ranch family's cabin; it does not identify that family as outlaws or establish an exact Cassidy residence. Dimensions, roof pitch, doorway, joinery, natural colour values and sandstone/juniper setting are reconstructed. Later ranch-house windows and shingles are excluded. The charred ruin is fictional game damage, not a reenactment of the reported cabin fire. Sources: https://npgallery.nps.gov/GetAsset/65cdf006-f91f-4a37-aac7-5576b6ab83e0 https://www.nps.gov/cany/learn/nature/utahjuniper.htm https://www.nps.gov/para/learn/nature/utah-juniper.htm https://www.nps.gov/colm/learn/nature/wingate-sandstone.htm https://research.fs.usda.gov/download/treesearch/62268.pdf"},
    {"holding-gallows", "Gallows",
     "Fort Smith rebuilt its oak gallows in 1886.\nTwelve steps led to a whitewashed platform.\nThis scaffold is a historical reconstruction.",
     "National Park Service, Fort Smith Gallows",
     "https://www.nps.gov/articles/000/fort-smith-gallows.htm",
     "Isolated Fort Smith, Arkansas scaffold of the roofed 1889-1890 type. Oak framing, twelve steps and whitewashing are documented; later reconstruction photographs guide detailed joinery, rails, roof surfacing and rope arrangement. The historic enclosure and adjacent masonry are omitted. Empty ropes represent preparation for use, not permanent installation or a particular execution. Ground treatment and exact colours are reconstructed. Damaged and ruined conditions are fictional game damage, not a documented historical fire. Sources: https://www.nps.gov/places/000/gallows.htm https://www.nps.gov/articles/000/fort-smith-then-and-now.htm https://research.fs.usda.gov/download/treesearch/62268.pdf"},
    {"holding-pony-express-station",
     "Pony Express Station",
     "Simpson Springs hosted the Pony Express.\nIts rock station saw stage use in the 1890s.\nThis building follows a later reconstruction.",
     "Bureau of Land Management; National Park Service",
     "https://www.nps.gov/places/simpson-springs-station.htm",
     "The scene depicts 1890s stage-station reuse at Simpson Springs, western Utah. BLM records refurbishment for Walters and Mulliner Stage Co. The architecture follows the 1975 reconstruction, informed by excavation and oral accounts; NPS cautions that the exact original Express building is uncertain. Dimensions, rear wall, closed door, material hues and individual stones are reconstructed. No active later Pony Express service is claimed. Sources: https://npshistory.com/publications/blm/cultresser/ut/2/sec2c.htm https://www.nps.gov/places/simpson-springs-station.htm The ruined condition is fictional game damage, not a documented Simpson Springs fire."},
    {"holding-chuckwagon", "Chuckwagon",
     "Charles Goodnight adapted an army wagon in 1866.\nIts pantry and fold-down table formed a kitchen.\nThis chuckwagon is a reconstruction.",
     "National Park Service, The Chuckwagon; Library of Congress",
     "https://www.nps.gov/places/the-chuckwagon.htm",
     "Reconstructed 1866–1900 cattle-drive kitchen, not an exact replica of Goodnight's first wagon. The NPS photograph shows a modern replica; the LOC photograph is monochrome and broadly dated approximately 1880–1910. Dimensions, pantry layout, running-gear details, canvas folds, cookware shapes and natural material colours are reconstruction. The charred wreck is fictional game damage, not a documented historical accident. Sources: https://www.nps.gov/places/the-chuckwagon.htm https://www.loc.gov/pictures/item/2012646304/"},
    {"holding-free-homestead",
     "Free Homestead",
     "George Palmer built a Nebraska cabin in 1867.\nHis family moved in the following spring.\nThis homestead cabin is a reconstruction.",
     "National Park Service, Palmer-Epard Cabin and interpretive history",
     "https://www.nps.gov/home/planyourvisit/p-ecabin.htm",
     "Palmer-Epard cabin type, southeastern Nebraska, represented before its 1875–1880 rear lean-to. Modern restored photographs inform materials and construction. Roof, openings, unseen rear, dimensions of details and colours are reconstruction; modern concrete and visitors are excluded. Burned-out condition is fictional game damage, not a documented cabin fire. Sources: https://www.nps.gov/home/planyourvisit/p-ecabin.htm https://www.nps.gov/media/video/view.htm?id=9BC4DD0C-8E8F-434C-A9D4-73D0B11AFCB9"},
    {"holding-courthouse", "Courthouse",
     "Cochise County built its courthouse in 1882.\nIts offices served a growing mining town.\nThis model reconstructs the early building.",
     "National Park Service, National Register nomination; Arizona Memory Project",
     "https://npgallery.nps.gov/GetAsset/fdd63b9c-ecad-4d08-8ac5-bb37cca1bd48",
     "1882 courthouse in Tombstone, Arizona Territory; simplified game-scale reconstruction, excluding the explicitly dated 1904 rear extension. NPS National Register nomination, 1970, sections 7–8. Inspected 1937 HABS views support surviving details but are later than the represented date. Rear fenestration, original chimney count, roof finish and exact colours are declared reconstruction. No particular judicial action is depicted. Burned-out condition is fictional game damage, not a documented courthouse fire. Sources: https://npgallery.nps.gov/GetAsset/fdd63b9c-ecad-4d08-8ac5-bb37cca1bd48 https://azmemory.azlibrary.gov/nodes/view/171746"},
    {"holding-lookout-ridge", "Lookout Ridge",
     "Hard limestone shields softer sediment.\nScotts Bluff stood beside the overland trails.\nThis miniature reconstructs a bluff type.",
     "National Park Service, Scotts Bluff geology and cultural landscape",
     "https://www.nps.gov/scbl/learn/nature/geologic-landforms.htm",
     "Reconstructed sedimentary bluff type near Scotts Bluff, western Nebraska, in an 1866 overland-trail context. Harder grey limestone concretions occur within softer sandstone and siltstone. The exact profile, fracture positions, colours and dry-grass placement are reconstructed, not a surveyed named summit or documented lookout installation. Modern photographs support geological materials and form, not an unchanged 1866 outline. Damaged and ruined conditions are fictional game states, not the documented October 2000 Saddle Rock fall or subsequent blasting. Sources: https://www.nps.gov/scbl/learn/nature/geologic-landforms.htm https://www.nps.gov/places/saddle-rock.htm https://www.nps.gov/subjects/culturallandscapes/centennialposterseries_mwr.htm https://www.nps.gov/scbl/learn/nature/plants.htm"},
    {"holding-rockslide-ridge", "Rockslide Ridge",
     "An 1872 earthquake shook Yosemite.\nFractured granite falls into talus slopes.\nThis ridge is a reconstructed landform.",
     "National Park Service, Yosemite geology and rockfall history",
     "https://www.nps.gov/places/000/geology-tour-john-muir-s-rockfall-experience-stop-7.htm",
     "The March 26, 1872 earthquake triggered Yosemite rockfalls:\nhttps://www.nps.gov/places/000/geology-tour-john-muir-s-rockfall-experience-stop-7.htm\nGranite fractures, sheeting and talus; modern colour photograph supports materials, not an 1872 cliff configuration:\nhttps://www.nps.gov/yose/learn/nature/rockfall.htm\nThe much older El Capitan avalanche is a different event:\nhttps://www.nps.gov/yose/learn/nature/investigating-the-el-capitan-rock-avalanche.htm\nMeadow-margin vegetation context:\nhttps://www.nps.gov/yose/learn/nature/meadows.htm\nExact ridge profile, fractures, hues and vegetation placement are reconstructed. Damaged and collapsed conditions are fictional game states, not a named historical fall or physical simulation. The miniature abstracts debris beyond its footprint."},
    {"holding-army-surgeons-tent", "Army Surgeon's Tent",
     "Army field hospitals used canvas tents.\nJohn Wiley used a wall tent in 1862-1864.\nThis portable shelter is a reconstruction.",
     "National Park Service; Lori Eggleston, museum curator; Library of Congress",
     "https://www.nps.gov/places/field-hospital-tour-stop-16.htm",
     "Medical tent context at Shiloh:\nhttps://www.nps.gov/places/field-hospital-tour-stop-16.htm\nCurator's account of John Wiley's army-duck tent and its use in 1862-1864:\nhttps://guardianoftheartifacts.blogspot.com/2012/07/an-army-surgeons-tent.html\nPetersburg surgeons' tent photograph, 1864:\nhttps://www.loc.gov/pictures/item/2018666674/\nThis miniature reconstructs the tent type, not Wiley's exact tent or a named Western hospital. Dimensions, rear wall, supports, guy spacing and clean material colours are reconstructed. The museum's modern display frame is excluded. The prairie base is a separate reconstructed setting:\nhttps://www.nps.gov/home/learn/nature/prairies.htm\nhttps://bwsr.state.mn.us/node/11071\nhttps://soilseries.sc.egov.usda.gov/OSD_Docs/W/WYMORE.html\nBurned-out condition is fictional game damage, not a documented tent fire."},
    {"holding-post-office", "Post Office",
     "Fort Laramie's post office served emigrants.\nIt occupied part of the sutler's store complex.\nThis detached stone miniature is a reconstruction.",
     "National Park Service, Post Office at Fort Laramie; Historical Handbook 20",
     "https://www.nps.gov/places/post-office-at-fort-laramie.htm",
     "NPS archival photograph and postal history:\nhttps://www.nps.gov/places/post-office-at-fort-laramie.htm\nThe NPS handbook distinguishes the circa 1852 stone section from the earlier adobe store and 1883 lime-concrete addition:\nhttps://npshistory.com/handbooks/historical/20/hh20s.htm\nThis miniature interprets later military postal use, 1883-1890. Its detached footprint, unseen rear, dimensions, small fittings and exact material hues are reconstructed. The archive photograph does not establish original colours. Bare-earth colour uses a regional analogy, not a courtyard soil survey:\nhttps://soilseries.sc.egov.usda.gov/OSD_Docs/B/BROWNRIGG.html\nRuined condition is fictional game damage, not a claim that the Fort Laramie post office burned."},
    {"holding-jailhouse", "Jailhouse",
     "Fort Smith built a new federal jail in 1888.\nIts tall barred windows lit three tiers of cells.\nThis detached miniature is a reconstruction.",
     "National Park Service, Fort Smith NHL nomination, 2015, pp. 16-17",
     "https://npshistory.com/publications/fosm/nr-fort-smith-2015.pdf",
     "NPS architectural description: brick walls, limestone window surrounds, slate roof, chimneys and ventilators.\nhttps://npshistory.com/publications/fosm/nr-fort-smith-2015.pdf\nEarly jail-wing postcard and vegetated foreground:\nhttps://www.nps.gov/fosm/learn/historyculture/new-jail-wing-c-1890.htm\nThe detached end walls, timber door, compact dimensions, exact hues and vegetation are reconstructed. The modern entrance is excluded. Ruined condition is fictional game damage, not a claim that this jail burned."},
    {"holding-gunsmith", "Gunsmith",
     "Freund & Brother had a Laramie gun shop in 1868.\nIts signs advertised firearms and ammunition.\nThis shop's rear and colours are reconstructed.",
     "Arundel C. Hull, 1868; Denver Public Library, Z-5809",
     "https://digital.denverlibrary.org/nodes/view/1115832",
     "Hull's 1868 photograph of Freund & Brother, Laramie, Wyoming Territory:\nhttps://digital.denverlibrary.org/nodes/view/1115832\nThe compact dimensions, rear, closed door, roof joinery, simplified lettering and material colours are reconstruction. The monochrome photograph cannot establish original paint hues.\nGround colour uses a modern regional soil analogue, not a survey of the historical street:\nhttps://soilseries.sc.egov.usda.gov/OSD_Docs/P/PILOTPEAK.html\nNative bluebunch wheatgrass form and leaf colour:\nhttps://research.fs.usda.gov/treesearch/44644\nExact grass placement and bunch density are reconstructed."},
    {"holding-wanted-poster-board", "Wanted Poster Board",
     "Missouri issued a reward proclamation in 1881.\nBill posters pasted paper onto lumber boards.\nThis small stand combines those practices.",
     "State Historical Society of Missouri; New York Clipper, April 8, 1871",
     "https://collections.shsmo.org/manuscripts/columbia/c2875",
     "Crittenden reward proclamation, 1881; inspected broadside:\nhttps://historicmissourians.shsmo.org/wp-content/uploads/2020/12/proclamation_lg.jpg\nLumber billboards and pasted bills, New York Clipper, April 8, 1871:\nhttps://classic.circushistory.org/Clipper/Clipper1870-71.htm\nExact stand, layout, wording and fresh material colours are reconstructed. The ground uses Kansas soil and native-grass analogues, not a surveyed historical site."},
    {"wounded-bandage", "The wound dressing",
     "An 1863 manual describes muslin roller bandages.\nThis dressing marks a game wound; its placement\nis reconstructed, not a recorded personal injury.",
     "John H. Packard, A manual of minor surgery, 1863, pp. 91, 95–97",
     "https://wellcomecollection.org/works/be7k5xq7",
     "Packard, 1863, pp. 91, 95–97: muslin strips and overlapping turns.\nhttps://wellcomecollection.org/works/be7k5xq7\nThe short wrap, placement over an unchanged sleeve where present, and undyed cloth colour are reconstructions. This is not a clinical demonstration or a claim about traditional medicine."},
    {"whiskey-supplies", "Hip Flask and bonus whiskey",
     "Amber pocket flasks came in strap-side forms.\nMcKee sold plain bar tumblers in 1868.\nThe bonus tumbler's exact profile is reconstructed.",
     "SHA / BLM bottle history; McKee & Brothers, 1868",
     "https://archive.org/details/pricesofglasswar00mcke",
     "Bill Lindsey / SHA-BLM, Liquor/Spirits Bottles\nhttps://secure-sha.org/bottle/liquor.htm\nMcKee & Brothers, Prices of Glass Ware, 1868\nhttps://archive.org/details/pricesofglasswar00mcke", "trail-delivery"},
    {"trail-delivery", "The delivery wagon and ox team",
     "Lighter Murphy trail wagons used two pairs of oxen.\nWooden yokes carried chains; the tongue steered.\nThis wagon, ox team and gait are reconstructions.",
     "National Park Service; Ford and Kreutzer, Overland Journal, 2015",
     "https://www.nps.gov/articles/000/wagons-on-the-trails.htm",
     "National Park Service, Wagons on the Trails\nhttps://www.nps.gov/articles/000/wagons-on-the-trails.htm\nFord and Kreutzer, Overland Journal, Spring 2015, pp. 9-11\nhttps://www.nps.gov/cali/learn/historyculture/upload/OJ-spring2015-oxen.pdf\nWhoop-Up Trail, National Register nomination, pp. 13-14 (paint colours)\nhttps://npgallery.nps.gov/NRHP/GetAsset/NRHP/64500348_text"},
    {"stampede", "Stampede",
     "Cattle could stampede without warning at night.\nRiders tried to turn the leaders into a wide circle\nto slow and gather the herd.",
     "National Park Service - Trail Drives",
     "https://www.nps.gov/grko/learn/historyculture/traildrives.htm"},
    {"drifter", "Drifter - a fictional frontier hand",
     "Kerchiefs protected cowboys' faces from dust.\nThey also covered the neck against the sun.\nThis stranger and his reveal are fictional.",
     "National Park Service - Pipe Spring, Cowboy Gear",
     "https://www.nps.gov/pisp/learn/photosmultimedia/cowboy-gear.htm"},
#include "OldWestCrewHistory.inl"
#include "OldWestHoldingsHistory.inl"
#include "OldWestTroubleHistory.inl"
};
inline const FNote* ForAsset(std::string_view Key)
{
    for (const auto& Note : Notes) if (Key == Note.Key) return &Note;
    return nullptr;
}
inline const FNote* ForVisibleCard(const nlohmann::ordered_json& Card)
{
    if (!Card.is_object()) return nullptr;
    // Always mask before looking up any identity, including owner-only peeks.
    if (Card.value("punk", false)) return ForAsset("drifter");
    const auto Id = Card.value("card_id", std::string());
    if (Id == "punk") return ForAsset("drifter");
    if (Id == "stampede") return ForAsset("stampede");
    if (Id == "hip_flask") return ForAsset("whiskey-supplies");
    if (const auto* Trouble = OldWestTrouble::ForCard(Id)) return ForAsset(Trouble->Key);
    // Camps are always face-up public cards; each base camp shows its holding.
    if (const auto* Holding = OldWestExpansionHoldings::ForCamp(Id)) return ForAsset(Holding->Key);
    if (const auto* Holding = OldWestHoldings::ForCamp(Id)) return ForAsset(Holding->Key);
    const auto Visual = OldWestCosmetics::Visual(Card);
    if (OldWestCrew::ForVisual(Visual)) return ForAsset(Visual);
    return nullptr;
}
inline const FNote* ForVisibleWound(const nlohmann::ordered_json& Card)
{
    if (!Card.is_object() || Card.value("damage", 0) != 1 || Card.value("destroyed", false)) return nullptr;
    const auto* Visible = ForVisibleCard(Card);
    if (!Visible || (std::string_view(Visible->Key) != "drifter" && !OldWestCrew::ForVisual(Visible->Key))) return nullptr;
    return ForAsset("wounded-bandage");
}
}
