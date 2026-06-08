import type { MedicationPlan } from '../types'
import { downloadText } from '../utils'

export const reminderAdapter = {
  async requestPermission() {
    if (!('Notification' in window)) return 'unsupported' as const
    return Notification.requestPermission()
  },

  notify(title: string, body: string) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, { body, icon: '/icons/u2.svg' })
      return true
    }
    return false
  },

  exportMedication(plan: MedicationPlan) {
    const events = plan.times.map((time, index) => {
      const [hour, minute] = time.split(':')
      return ['BEGIN:VEVENT', `UID:${plan.id}-${index}@u2.local`, `DTSTART:${new Date().toISOString().slice(0, 10).replaceAll('-', '')}T${hour}${minute}00`, 'RRULE:FREQ=DAILY', `SUMMARY:服用 ${plan.name}`, `DESCRIPTION:${plan.dose}${plan.requirement ? ` · ${plan.requirement}` : ''}`, 'END:VEVENT'].join('\r\n')
    }).join('\r\n')
    const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//U2//Medication Reminder//ZH-CN', events, 'END:VCALENDAR'].join('\r\n')
    downloadText(`${plan.name}-用药提醒.ics`, ics, 'text/calendar;charset=utf-8')
  },
}
