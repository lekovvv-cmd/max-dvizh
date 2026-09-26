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
      <p>Выбери когда и куда.</p>
      <button type="button" className="primary-button" onClick={onSignal}>
        Подать сигнал
      </button>
      <div className="home-intro__repeat">
        <div>
          <strong>{hasRepeat ? 'Регулярный сигнал настроен' : 'Ходите куда-то регулярно?'}</strong>
        </div>
        <button type="button" className="text-action" onClick={onRepeat}>
          {hasRepeat ? 'Изменить' : 'Настроить'}
        </button>
      </div>
    </section>
  )
}
