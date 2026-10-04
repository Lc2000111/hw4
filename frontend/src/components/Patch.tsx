// A chenille "varsity letter" patch: scalloped edge + stitched ring + block letters.
// Used for the logo, the chat avatar, and the chat launcher.
interface Props {
  text?: string
  size?: number
  className?: string
}

const SCALLOPS = 18

export default function Patch({ text = 'CC', size = 40, className = '' }: Props) {
  // Scalloped outline: a circle of overlapping bumps.
  const bumps = Array.from({ length: SCALLOPS }, (_, i) => {
    const a = (i / SCALLOPS) * Math.PI * 2
    return <circle key={i} cx={50 + Math.cos(a) * 42} cy={50 + Math.sin(a) * 42} r={9} />
  })
  return (
    <svg className={`patch ${className}`} width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <g className="patch-edge">
        {bumps}
        <circle cx="50" cy="50" r="42" />
      </g>
      <circle className="patch-face" cx="50" cy="50" r="38" />
      <circle className="patch-stitch" cx="50" cy="50" r="33" />
      <text className="patch-text" x="50" y="52" textAnchor="middle" dominantBaseline="middle">
        {text}
      </text>
    </svg>
  )
}
