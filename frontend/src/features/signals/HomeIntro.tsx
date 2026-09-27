import { PulseMark } from '../../shared/ui/PulseMark'

export function HomeIntro({
  onSignal,
  onRepeat,
  repeatStatus,
}: {
  onSignal: () => void
  onRepeat: () => void
  repeatStatus?: string
}) {
  return (
    <section className="home-intro" aria-labelledby="home-title">
      <PulseMark />
      <h1 id="home-title">Есть идея на вечер?</h1>
      <button type="button" className="primary-button" onClick={onSignal}>
        Подать сигнал
      </button>
      <div className="home-intro__repeat">
        <div>
          <strong>
            {repeatStatus === 'PAUSED'
              ? 'Регулярный сигнал приостановлен'
              : repeatStatus === 'ACTIVE'
                ? 'Регулярный сигнал настроен'
                : 'Ходите куда-то регулярно?'}
          </strong>
        </div>
        <button type="button" className="text-action" onClick={onRepeat}>
          {repeatStatus ? 'Изменить' : 'Настроить'}
        </button>
      </div>
    </section>
  )
}
