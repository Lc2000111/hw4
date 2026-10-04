import { Link } from 'react-router-dom'

export default function About() {
  return (
    <article className="about">
      <p className="eyebrow">About Us</p>
      <h1>
        A New Haven shop with a lot of <span>Bulldog blue</span>.
      </h1>

      <p className="lead">
        Campus Customs is a Yale apparel shop at 57 Broadway, just steps from campus. We think
        school spirit should feel good to wear, so everything we carry is officially licensed
        and chosen because it's comfortable, holds up, and looks sharp.
      </p>

      <div className="about-grid">
        <section>
          <h2>What we carry</h2>
          <p>
            Classic crewnecks, pullover and full-zip hoodies, quarter-zips, fleece jackets, and
            everyday tees. You'll find the big YALE wordmark, vintage bulldogs, residential
            college crests, and left-chest designs for varsity teams from crew to fencing.
          </p>
        </section>
        <section>
          <h2>Who we serve</h2>
          <p>
            First-years buying their first hoodie, seniors who want something to remember the
            place by, parents on move-in weekend, and alumni back for The Game. Whatever your
            connection to Yale, you belong here.
          </p>
        </section>
        <section>
          <h2>How we help</h2>
          <p>
            Not sure about a size or a color? Ask the chat assistant in the corner of any page.
            It looks up live prices and stock from our inventory, so you get a straight answer
            instead of a guess.
          </p>
        </section>
      </div>

      <div className="about-visit">
        <div>
          <h2>Come say hi</h2>
          <p>57 Broadway, New Haven, CT 06511</p>
        </div>
        <Link to="/products" className="btn">
          Browse products
        </Link>
      </div>
    </article>
  )
}
