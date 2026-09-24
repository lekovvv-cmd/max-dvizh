import { PulseMark } from '../../shared/ui/PulseMark'

export function HomeIntro({
  onSignal,
  onRepeat,
  hasRepeat,
}: {
  onSignal: () => void
  onRepeat: () => void
  hasRepeat?: boolean
}) {
  return (
    <section className="home-intro" aria-labelledby="home-title">
      <PulseMark />
      <h1 id="home-title">Есть идея на вечер?</h1>
      <p>Скажи, когда и что хочется. Остальных спросит ДВИЖ.</p>
      <button type="button" className="primary-button" data-coach="signal" onClick={onSignal}>
        Подать сигнал
      </button>
      <p className="home-intro__steps">
        Подай сигнал <span>→</span> выбери место <span>→</span> остальное сделает ДВИЖ
      </p>
      <div className="home-intro__repeat">
        <div>
          <strong>{hasRepeat ? 'Регулярный сигнал настроен' : 'Собираетесь регулярно?'}</strong>
          <p>
            {hasRepeat
              ? 'Можно изменить дни, время и условия.'
              : 'Настрой повторение, например каждую пятницу.'}
          </p>
        </div>
        <button type="button" className="text-action" onClick={onRepeat}>
          {hasRepeat ? 'Изменить' : 'Настроить'}
        </button>
      </div>
    </section>
  )
}
