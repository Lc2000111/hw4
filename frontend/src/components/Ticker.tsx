// Scoreboard-style ticker under the nav. Only true facts: no invented sales or shipping promises.
const ITEMS = [
  'Officially licensed Yale apparel',
  '57 Broadway · New Haven',
  'Live stock, checked by our assistant',
  'Hoodies · Crewnecks · Tees · Quarter-zips · Jackets',
  'XS to XXL',
  'Boola Boola',
]

export default function Ticker() {
  const row = ITEMS.map((t) => (
    <span key={t}>
      {t}
      <i aria-hidden="true">✦</i>
    </span>
  ))
  return (
    <div className="ticker" aria-label="Campus Customs highlights">
      <div className="ticker-track">
        {row}
        <span aria-hidden="true" className="ticker-dup">
          {row}
        </span>
      </div>
    </div>
  )
}
