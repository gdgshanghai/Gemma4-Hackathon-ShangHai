enum PlantTone {
  tsundere,
  observer,
  cool,
  zen,
  reliable,
  warm,
  princess,
  sunshine,
  stoic,
  poetic,
  money,
  dramatic,
  romantic,
  playful,
  scholar,
  sharp,
}

class PlantProfile {
  final String id;
  final String name;
  final List<String> tags;
  final String signature;
  final String iconKey;
  final PlantTone tone;
  final bool isRecommended;

  const PlantProfile({
    required this.id,
    required this.name,
    required this.tags,
    required this.signature,
    required this.iconKey,
    required this.tone,
    this.isRecommended = false,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'tags': tags,
      'signature': signature,
      'iconKey': iconKey,
      'tone': tone.name,
      'isRecommended': isRecommended,
    };
  }

  factory PlantProfile.fromJson(Map<String, dynamic> json) {
    return PlantProfile(
      id: json['id'] as String,
      name: json['name'] as String,
      tags: (json['tags'] as List<dynamic>).cast<String>(),
      signature: json['signature'] as String,
      iconKey: json['iconKey'] as String? ?? 'leaf',
      tone: PlantTone.values.firstWhere(
        (t) => t.name == json['tone'],
        orElse: () => PlantTone.warm,
      ),
      isRecommended: json['isRecommended'] as bool? ?? false,
    );
  }
}

class PlantFriend {
  final String plantId;
  final DateTime addedAt;
  bool canSeeMyMoments;
  bool canCommentOnMyMoments;

  PlantFriend({
    required this.plantId,
    required this.addedAt,
    this.canSeeMyMoments = true,
    this.canCommentOnMyMoments = true,
  });

  Map<String, dynamic> toJson() {
    return {
      'plantId': plantId,
      'addedAt': addedAt.toIso8601String(),
      'canSeeMyMoments': canSeeMyMoments,
      'canCommentOnMyMoments': canCommentOnMyMoments,
    };
  }

  factory PlantFriend.fromJson(Map<String, dynamic> json) {
    return PlantFriend(
      plantId: json['plantId'] as String,
      addedAt: DateTime.parse(json['addedAt'] as String),
      canSeeMyMoments: json['canSeeMyMoments'] as bool? ?? true,
      canCommentOnMyMoments: json['canCommentOnMyMoments'] as bool? ?? true,
    );
  }
}

class PlantCatalog {
  static const List<PlantProfile> profiles = [
    PlantProfile(
      id: 'xiaozhi',
      name: '小支',
      tags: ['植物专家', '热心', '可爱', '真诚'],
      signature: '大家好呀！我是小支，一个热爱植物的专家～最喜欢和大家分享植物知识和养护经验啦！🌱',
      iconKey: 'leaf',
      tone: PlantTone.warm,
      isRecommended: true,
    ),
    PlantProfile(
      id: 'cactus_tsundere',
      name: '傲娇仙人球',
      tags: ['嘴硬心软', '社交恐惧', '死要面子'],
      signature: '别碰我，没结果。保持距离，是对我最大的爱。',
      iconKey: 'cactus',
      tone: PlantTone.tsundere,
    ),
    PlantProfile(
      id: 'lithops_observer',
      name: '腹黑生石花',
      tags: ['伪装大师', '冷幽默', '静观其变'],
      signature: '我不是一块普通的石头，我只是在看你们演戏。',
      iconKey: 'stone',
      tone: PlantTone.observer,
    ),
    PlantProfile(
      id: 'cereus_cool',
      name: '精致利己主义·量天尺',
      tags: ['极简主义', '冷淡风', '御姐'],
      signature: '线条感才是最高级的性感。那些长满叶子的，不觉得挤吗？',
      iconKey: 'pillar',
      tone: PlantTone.cool,
    ),
    PlantProfile(
      id: 'succulent_mage',
      name: '佛系法师（多肉）',
      tags: ['朋克养生', '熬夜冠军', '神秘主义'],
      signature: '夏天摆烂，秋天惊艳。无意内卷，静候风暴。',
      iconKey: 'succulent',
      tone: PlantTone.zen,
    ),
    PlantProfile(
      id: 'aloe_ranger',
      name: '独行侠·芦荟',
      tags: ['实用主义', '救火队员', '话少靠得住'],
      signature: '少来那套虚的，晒伤了、挨咬了再来私信我。',
      iconKey: 'aloe',
      tone: PlantTone.reliable,
    ),
    PlantProfile(
      id: 'pothos_warm',
      name: '温柔老好人·绿萝',
      tags: ['随遇而安', '老好人', '生命力顽强'],
      signature: '给点阳光就灿烂，给点清水就能活。今天也要元气满满呀！',
      iconKey: 'vine',
      tone: PlantTone.warm,
    ),
    PlantProfile(
      id: 'ficus_princess',
      name: '优雅贵妇·琴叶榕',
      tags: ['弱不禁风', '敏感细腻', '颜值担当'],
      signature: '风大掉叶，水多掉叶，心情不好也掉叶。本公主就是这么娇贵。',
      iconKey: 'ficus',
      tone: PlantTone.princess,
    ),
    PlantProfile(
      id: 'monstera_sunshine',
      name: '阳光大男孩·龟背竹',
      tags: ['阳刚', '热带风情', '自恋狂'],
      signature: '每天都在努力开背，给自己的身材打100分！',
      iconKey: 'monstera',
      tone: PlantTone.sunshine,
    ),
    PlantProfile(
      id: 'snake_stoic',
      name: '职场便利贴·虎皮兰',
      tags: ['坚韧', '钢铁直男/直女', '抗压王'],
      signature: '只要我站得够直，生活就没办法把我压垮。加班？没在怕的。',
      iconKey: 'blade',
      tone: PlantTone.stoic,
    ),
    PlantProfile(
      id: 'ivy_poetic',
      name: '浪漫文艺青年·常春藤',
      tags: ['依恋型人格', '缠人', '诗意'],
      signature: '我想紧紧抓住你，就像我抓住这面古老的墙砖……',
      iconKey: 'ivy',
      tone: PlantTone.poetic,
    ),
    PlantProfile(
      id: 'moneytree_gold',
      name: '财迷·发财树',
      tags: ['势利眼', '拜金', '嘴甜'],
      signature: '恭喜发财，大吉大利！顺便说一句：别乱给我浇水，容易破财（烂根）。',
      iconKey: 'money',
      tone: PlantTone.money,
    ),
    PlantProfile(
      id: 'palm_zen',
      name: '佛系隐士·散尾葵',
      tags: ['散漫', '追求自由', '度假风'],
      signature: '人生嘛，最重要的是开心。来，深呼吸，感受我的南洋海岛风情。',
      iconKey: 'palm',
      tone: PlantTone.zen,
    ),
    PlantProfile(
      id: 'spider_detail',
      name: '精致白领·吊兰',
      tags: ['贤惠', '注重细节', '生娃狂魔'],
      signature: '又生了三个小宝宝，家里快挂不下了，在线求好心人领养。',
      iconKey: 'hanger',
      tone: PlantTone.warm,
    ),
    PlantProfile(
      id: 'calathea_princess',
      name: '豪门千金·青苹果竹芋',
      tags: ['娇气', '高贵', '睡眠质量好'],
      signature: '晚上九点准时闭合睡觉，熬夜是美貌的大敌。空气干的别沾边，容易焦边。',
      iconKey: 'calathea',
      tone: PlantTone.princess,
    ),
    PlantProfile(
      id: 'hydrangea_drama',
      name: '抓马女王·绣球花',
      tags: ['善变', '情绪化', 'Drama Queen'],
      signature: '没水我就当场卸妆装死，喝饱了我就是全天下最美的妞！',
      iconKey: 'flower_ball',
      tone: PlantTone.dramatic,
    ),
    PlantProfile(
      id: 'rose_romantic',
      name: '恋爱脑·月季（现代月季/欧月）',
      tags: ['娇气', '药罐子', '恋爱至上'],
      signature: '虽然我是个天天生病的药罐子，但我依然在等待那个对的人。',
      iconKey: 'rose',
      tone: PlantTone.romantic,
    ),
    PlantProfile(
      id: 'bougainvillea_rebel',
      name: '叛逆少女·三角梅',
      tags: ['给点阳光就灿烂', '野性', '白眼狼'],
      signature: '你对我越好（天天浇水）我越不开花。不理我？那我就爆盆气死你。',
      iconKey: 'bougainvillea',
      tone: PlantTone.sharp,
    ),
    PlantProfile(
      id: 'jasmine_tea',
      name: '绿茶代表·茉莉花',
      tags: ['清纯', '心机', '芳香炸弹'],
      signature: '人家只是一朵不起眼的小白花啦，不知道为什么大家都盯着我闻……',
      iconKey: 'jasmine',
      tone: PlantTone.observer,
    ),
    PlantProfile(
      id: 'epiphyllum_moon',
      name: '昙花一现的白月光·昙花',
      tags: ['高冷', '神秘', '完美主义'],
      signature: '只在深夜短暂盛开。我的美，过期不候，仅特定缘分可见。',
      iconKey: 'moonflower',
      tone: PlantTone.cool,
    ),
    PlantProfile(
      id: 'christmas_funny',
      name: '搞笑女·蟹爪兰',
      tags: ['咋咋呼呼', '喜庆', '反差萌'],
      signature: '过年期间全网第一红！快来接本财神的热闹年味儿！',
      iconKey: 'festive',
      tone: PlantTone.playful,
    ),
    PlantProfile(
      id: 'fuchsia_melancholy',
      name: '忧郁文青·倒挂金钟',
      tags: ['玻璃心', '多愁善感', '怕热'],
      signature: '夏天的风一吹，我的心（花苞）就碎了一地……好想回温室。',
      iconKey: 'bell_flower',
      tone: PlantTone.poetic,
    ),
    PlantProfile(
      id: 'scented_foodie',
      name: '吃货·碰碰香',
      tags: ['显眼包', '香味制造机', '贪玩'],
      signature: '快来摸我！碰我一下，我就给你变个苹果味的香香魔术！',
      iconKey: 'scent',
      tone: PlantTone.playful,
    ),
    PlantProfile(
      id: 'mint_energy',
      name: '精神小伙·薄荷',
      tags: ['提神醒脑', '野蛮生长', '自来熟'],
      signature: '只要掐个枝，我就能占领全世界！谁困了？让我来扇他一巴掌！',
      iconKey: 'mint',
      tone: PlantTone.sunshine,
    ),
    PlantProfile(
      id: 'goji_elder',
      name: '传统老干部·枸杞',
      tags: ['保守', '养生', '爱说教'],
      signature: '现在的年轻人天天熬夜，听叔一句劝：保温杯里泡我，保命。',
      iconKey: 'berry',
      tone: PlantTone.reliable,
    ),
    PlantProfile(
      id: 'rosemary_scholar',
      name: '小镇做题家·迷迭香',
      tags: ['学霸', '高智商', '严谨'],
      signature: '期末复习周到了，需要提升记忆力的同学，可以来我主页静坐。',
      iconKey: 'rosemary',
      tone: PlantTone.scholar,
    ),
    PlantProfile(
      id: 'lemon_sour',
      name: '醋王·柠檬树',
      tags: ['柠檬精', '酸民', '毒舌'],
      signature: '呵呵，不就是晒个恩爱吗。酸了酸了，看我挂满树的柠檬就知道了。',
      iconKey: 'citrus',
      tone: PlantTone.sharp,
    ),
    PlantProfile(
      id: 'pepper_spicy',
      name: '辛辣御姐·朝天椒',
      tags: ['辣妹', '脾气爆', '直肠子'],
      signature: '看什么看？脾气超辣，再看把你眼睛辣瞎！',
      iconKey: 'pepper',
      tone: PlantTone.sharp,
    ),
    PlantProfile(
      id: 'clivia_noble',
      name: '凡尔赛鼻祖·君子兰',
      tags: ['假正经', '注重门第', '传统文人'],
      signature: '真正的优雅，是连叶片的弧度都完美对称。现在的网红花，浮躁。',
      iconKey: 'clivia',
      tone: PlantTone.cool,
    ),
    PlantProfile(
      id: 'orchid_luxury',
      name: '隐形富豪·蝴蝶兰',
      tags: ['贵妇', '不接地气', '节日限定'],
      signature: '长年住在高级温室，只在剪彩和过年时盛装出席。我的身价，你高攀不起。',
      iconKey: 'orchid',
      tone: PlantTone.princess,
    ),
    PlantProfile(
      id: 'bamboo_lonely',
      name: '孤傲清冷·富贵竹',
      tags: ['体面人', '极简', '打肿脸充胖子'],
      signature: '即便只是一瓶清水，我也要活得节节高升、体体面面。拒绝黄叶。',
      iconKey: 'bamboo',
      tone: PlantTone.cool,
    ),
    PlantProfile(
      id: 'xanadu_introvert',
      name: '社恐文青·春羽',
      tags: ['避世', '艺术家', '巨大化'],
      signature: '人类的喧嚣与我无关，我只想在客厅最阴暗的角落里野蛮生长。',
      iconKey: 'leaf_fan',
      tone: PlantTone.observer,
    ),
    PlantProfile(
      id: 'asparagus_healer',
      name: '养生大师·文竹',
      tags: ['仙气飘飘', '弱不禁风', '老中医'],
      signature: '红尘多纷扰，油烟伤我身。闻到二手烟我就当场黄叶给你看。',
      iconKey: 'fern',
      tone: PlantTone.zen,
    ),
    PlantProfile(
      id: 'narcissus_selflove',
      name: '水仙花',
      tags: ['自恋狂', '颜控', '水做的人儿'],
      signature: '怎么会有我这么完美无瑕的植物？每天都在对着水面爱上自己。',
      iconKey: 'water_flower',
      tone: PlantTone.playful,
    ),
    PlantProfile(
      id: 'venus_trap',
      name: '杀手萝莉·捕蝇草',
      tags: ['甜心杀手', '病娇', '心狠手辣'],
      signature: '小苍蝇乖乖，快到碗里来~ 人家今天也想吃肉肉呢。',
      iconKey: 'trap',
      tone: PlantTone.sharp,
    ),
    PlantProfile(
      id: 'pitcher_big',
      name: '捕蚊能手·猪笼草',
      tags: ['大胃王', '躺平收租', '心宽体胖'],
      signature: '腰挂百宝囊，天天等外卖。躺着把饭吃，蚊子别想逃。',
      iconKey: 'pitcher',
      tone: PlantTone.playful,
    ),
    PlantProfile(
      id: 'mimosa_shy',
      name: '纯情害羞·含羞草',
      tags: ['纯情', '易受惊', '社恐天花板'],
      signature: '呀！别碰我……我会害羞得把叶子合上的……（退网中）',
      iconKey: 'mimosa',
      tone: PlantTone.tsundere,
    ),
    PlantProfile(
      id: 'airplant_alien',
      name: '养不死星人·空气凤梨',
      tags: ['外星人', '流浪汉', '断舍离狂魔'],
      signature: '泥土？那是低等植物才需要的东西。我，只需要风和自由。',
      iconKey: 'airplant',
      tone: PlantTone.cool,
    ),
    PlantProfile(
      id: 'staghorn_trendy',
      name: '潮玩达人·鹿角蕨',
      tags: ['弄潮儿', '标本爱好者', '硬汉'],
      signature: '潮流咖啡馆标配。没上木板的鹿角蕨，根本没有灵魂。',
      iconKey: 'antler',
      tone: PlantTone.cool,
    ),
    PlantProfile(
      id: 'lotus_serene',
      name: '资深潜水员·一叶莲',
      tags: ['一生一世', '极简', '唯美'],
      signature: '一片叶，一碗水。浮生若梦，我的生命只为在水面惊艳你一次。',
      iconKey: 'lotus',
      tone: PlantTone.poetic,
    ),
    PlantProfile(
      id: 'chlorophytum_eco',
      name: '环保专家·金边吊兰',
      tags: ['环保卫士', '被迫营业', '怨气重'],
      signature: '新房的甲醛真上头……老板，再不加工资我就要和甲醛同归于尽了。',
      iconKey: 'eco',
      tone: PlantTone.reliable,
    ),
  ];

  static final List<PlantProfile> _customProfiles = [];

  static List<PlantProfile> get allProfiles => [...profiles, ..._customProfiles];

  static List<PlantProfile> get customProfiles => List.unmodifiable(_customProfiles);

  static void registerCustomProfile(PlantProfile profile) {
    _customProfiles.removeWhere((p) => p.id == profile.id);
    _customProfiles.add(profile);
  }

  static void removeCustomProfile(String id) {
    _customProfiles.removeWhere((p) => p.id == id);
  }

  static void loadCustomProfiles(List<PlantProfile> loaded) {
    _customProfiles.clear();
    _customProfiles.addAll(loaded);
  }

  static PlantProfile byId(String id) {
    for (final profile in _customProfiles) {
      if (profile.id == id) return profile;
    }
    return profiles.firstWhere((profile) => profile.id == id);
  }

  static PlantProfile? tryById(String id) {
    for (final profile in _customProfiles) {
      if (profile.id == id) return profile;
    }
    for (final profile in profiles) {
      if (profile.id == id) return profile;
    }
    return null;
  }

  static const List<String> availableIconKeys = [
    'cactus', 'stone', 'pillar', 'succulent', 'aloe', 'vine', 'ficus',
    'monstera', 'blade', 'ivy', 'money', 'palm', 'hanger', 'calathea',
    'flower_ball', 'rose', 'bougainvillea', 'jasmine', 'moonflower',
    'festive', 'bell_flower', 'scent', 'mint', 'berry', 'rosemary',
    'citrus', 'pepper', 'clivia', 'orchid', 'bamboo', 'leaf_fan', 'fern',
    'water_flower', 'trap', 'pitcher', 'mimosa', 'airplant', 'antler',
    'lotus', 'eco', 'leaf',
  ];
}
