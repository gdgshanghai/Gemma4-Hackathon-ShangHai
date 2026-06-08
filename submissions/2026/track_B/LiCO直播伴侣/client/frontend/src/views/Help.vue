<template>
  <div class="help-page">
    <div class="help-hero">
      <div>
        <div class="help-kicker">{{ $t('help.kicker') }}</div>
        <h1>{{ $t('help.heroTitle') }}</h1>
        <p class="help-subtitle">{{ $t('help.heroSubtitle') }}</p>
      </div>
      <div class="help-actions">
        <el-button type="primary" icon="el-icon-back" @click="$router.push({ name: 'home' })">
          {{ $t('help.backHome') }}
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="help-grid">
      <el-col v-for="section in sections" :key="section.title" :xs="24" :md="12">
        <el-card class="help-card help-section-card" shadow="hover">
          <div class="section-head">
            <div>
              <div class="step-badge">{{ section.badge }}</div>
              <h3>{{ section.title }}</h3>
            </div>
            <div class="section-type">{{ section.type }}</div>
          </div>
          <p class="section-desc">{{ section.desc }}</p>
          <ol class="section-list">
            <li v-for="item in section.items" :key="item">{{ item }}</li>
          </ol>
          <div class="section-footer">
            <el-link v-if="section.link" :href="section.link" target="_blank" type="primary">
              {{ section.linkText }}
            </el-link>
            <span v-if="section.note" class="section-note">{{ section.note }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="help-card help-notice">
      <div slot="header" class="card-header">
        <span>{{ $t('help.noticeTitle') }}</span>
      </div>
      <p>{{ $t('help.noticeBody') }}</p>
      <p>
        <el-link href="https://github.com/xfgryujk/blivechat/wiki/%E6%B3%A8%E6%84%8F%E4%BA%8B%E9%A1%B9%E5%92%8C%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98" target="_blank" type="primary">
          {{ $t('help.faqLink') }}
        </el-link>
      </p>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'Help',
  computed: {
    sections() {
      return [
        {
          badge: '01',
          type: this.$t('help.tagOnline'),
          title: this.$t('help.onlineTitle'),
          desc: this.$t('help.onlineDesc'),
          items: [
            this.$t('help.onlineStep1'),
            this.$t('help.onlineStep2'),
            this.$t('help.onlineStep3'),
            this.$t('help.onlineStep4')
          ],
          link: 'https://blive.chat/',
          linkText: this.$t('help.openOnlineLink'),
          note: this.$t('help.onlineNote')
        },
        {
          badge: '02',
          type: this.$t('help.tagLocal'),
          title: this.$t('help.localTitle'),
          desc: this.$t('help.localDesc'),
          items: [
            this.$t('help.localStep1'),
            this.$t('help.localStep2'),
            this.$t('help.localStep3'),
            this.$t('help.localStep4')
          ],
          link: 'https://github.com/xfgryujk/blivechat/releases',
          linkText: this.$t('help.openReleaseLink'),
          note: this.$t('help.localNote')
        },
        {
          badge: '03',
          type: this.$t('help.tagSource'),
          title: this.$t('help.sourceTitle'),
          desc: this.$t('help.sourceDesc'),
          items: [
            this.$t('help.sourceStep1'),
            this.$t('help.sourceStep2'),
            this.$t('help.sourceStep3'),
            this.$t('help.sourceStep4')
          ],
          note: this.$t('help.sourceNote')
        },
        {
          badge: '04',
          type: this.$t('help.tagDocker'),
          title: this.$t('help.dockerTitle'),
          desc: this.$t('help.dockerDesc'),
          items: [
            this.$t('help.dockerStep1'),
            this.$t('help.dockerStep2')
          ],
          note: this.$t('help.dockerNote')
        }
      ]
    }
  },
  methods: {}
}
</script>

<style scoped>
.help-page {
  min-height: 100vh;
  padding: 32px 24px 48px;
  background: linear-gradient(180deg, rgba(245, 242, 255, 0.88), rgba(255, 255, 255, 0.92));
}

.help-hero {
  max-width: 1200px;
  margin: 0 auto 24px;
  padding: 28px 30px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(121, 100, 230, 0.14), rgba(202, 189, 255, 0.22));
  border: 1px solid rgba(121, 100, 230, 0.12);
  box-shadow: 0 18px 50px rgba(121, 100, 230, 0.08);
}

.help-kicker {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  color: #7964e6;
  background: rgba(255, 255, 255, 0.75);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.help-hero h1 {
  margin: 12px 0 8px;
  font-size: 34px;
  line-height: 1.1;
  color: #312b4b;
}

.help-subtitle {
  max-width: 760px;
  margin: 0;
  color: #6c658a;
  font-size: 15px;
}

.help-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.help-card {
  max-width: 1200px;
  margin: 0 auto 20px;
  border: none;
  border-radius: 22px;
  box-shadow: 0 16px 40px rgba(121, 100, 230, 0.08);
}

.card-header {
  font-weight: 700;
  color: #312b4b;
}

.help-overview :deep(.el-card__body) {
  padding-top: 24px;
}

.help-note {
  margin: 0;
  color: #6c658a;
  line-height: 1.75;
}

.help-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.help-tag {
  display: inline-flex;
  align-items: center;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(121, 100, 230, 0.1);
  color: #7964e6;
  font-size: 12px;
  font-weight: 700;
}

.help-grid {
  max-width: 1240px;
  margin: 0 auto;
}

.help-section-card {
  margin-bottom: 20px;
  overflow: hidden;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.section-type {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(121, 100, 230, 0.08);
  color: #7964e6;
  font-size: 12px;
  font-weight: 700;
}

.step-badge {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: #7964e6;
  background: rgba(121, 100, 230, 0.1);
}

.help-section-card h3 {
  margin: 0 0 8px;
  color: #312b4b;
}

.section-desc {
  margin: 0 0 14px;
  color: #6c658a;
  line-height: 1.65;
}

.section-list {
  margin: 0;
  padding-left: 18px;
  color: #4a4563;
  line-height: 1.75;
}

.section-list li + li {
  margin-top: 8px;
}

.section-footer {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.section-note {
  color: #7c7694;
  font-size: 13px;
}

.help-shot {
  width: 100%;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 12px 28px rgba(49, 43, 75, 0.08);
}

.help-notice {
  margin-top: 6px;
}

@media (max-width: 768px) {
  .help-page {
    padding: 20px 14px 32px;
  }

  .help-hero {
    padding: 22px 18px;
    flex-direction: column;
    align-items: flex-start;
  }

  .help-hero h1 {
    font-size: 26px;
  }

  .section-head {
    flex-direction: column;
  }
}
</style>
