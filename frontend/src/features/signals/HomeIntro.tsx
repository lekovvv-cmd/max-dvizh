import { PulseMark } from '../../shared/ui/PulseMark'
import { Icon } from '../../shared/ui/Icon'

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
      <div className="home-intro__hero">
        <div className="home-intro__copy">
          <h1 id="home-title">Есть идея на вечер?</h1>
          <p>Подай сигнал. Выбери место. Остальное сделает ДВИЖ</p>
        </div>
        <PulseMark />
        <button type="button" className="primary-button" onClick={onSignal}>
          Подать сигнал
        </button>
      </div>
      <div className="home-intro__repeat">
        <div>
          <h2>
            {repeatStatus === 'PAUSED'
              ? 'Регулярный сигнал приостановлен'
              : repeatStatus === 'ACTIVE'
                ? 'Регулярный сигнал настроен'
                : 'Ходите куда-то регулярно?'}
          </h2>
          <p>{repeatStatus ? 'Измени расписание или условия' : 'Создай повтор каждую неделю'}</p>
        </div>
        <button type="button" className="home-intro__repeat-action" onClick={onRepeat}>
          <Icon name="plus" size={24} />
          <span className="visually-hidden">{repeatStatus ? 'Изменить' : 'Настроить'}</span>
        </button>
      </div>
    </section>
  )
}
