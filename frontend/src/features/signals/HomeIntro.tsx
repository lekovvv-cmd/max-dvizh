import { PulseMark } from '../../shared/ui/PulseMark'

export function HomeIntro({ onSignal, onRepeat }: { onSignal: () => void; onRepeat: () => void }) {
  return (
    <section className="home-intro" aria-labelledby="home-title">
      <PulseMark />
      <h1 id="home-title">Когда двигаемся?</h1>
      <p>Сигнал — это когда и куда ты готов пойти. ДВИЖ найдёт общий вариант для друзей.</p>
      <button type="button" className="primary-button" onClick={onSignal}>
        Подать сигнал
      </button>
      <p className="home-intro__steps">
        Выбрали условия <span>→</span> получили приглашение <span>→</span> план собран
      </p>
      <div className="home-intro__repeat">
        <div>
          <strong>Собираетесь регулярно?</strong>
          <p>Настрой повторение, например каждую пятницу.</p>
        </div>
        <button type="button" className="text-action" onClick={onRepeat}>
          Настроить
        </button>
      </div>
    </section>
  )
}
