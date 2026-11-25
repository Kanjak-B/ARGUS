import type { Core } from 'cytoscape'

const BACKGROUND = '#0b1120'
const MARGIN = 60
const CAPTION_HEIGHT = 50

function loadImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error("L'image n'a pas pu être générée"))
    image.src = source
  })
}

/** Image des seuls équipements qui répondent et des liens entre eux. */
function renderOnline(cy: Core) {
  const silent = cy.nodes('[status]').filter((node) => node.data('status') !== 'ok')
  const online = cy.nodes('[status = "ok"]')
  const emptyTitles = cy
    .nodes('[layerTitle]')
    .filter((title) => online.filter(`[layer = "${title.data('layerTitle')}"]`).empty())
  const hidden = silent.union(emptyTitles)
  const selected = cy.$(':selected')

  selected.unselect()
  hidden.addClass('export-hidden')
  try {
    // Le rendu est synchrone : l'écran n'a pas le temps d'afficher cet état intermédiaire
    return cy.png({
      output: 'base64uri',
      full: true,
      scale: 2,
      bg: BACKGROUND,
      maxWidth: 6000,
      maxHeight: 6000,
    })
  } finally {
    hidden.removeClass('export-hidden')
    selected.select()
  }
}

export async function exportPng(cy: Core, caption: string, filename: string) {
  const graph = await loadImage(renderOnline(cy))

  const canvas = document.createElement('canvas')
  canvas.width = Math.max(graph.width + 2 * MARGIN, 900)
  canvas.height = graph.height + 2 * MARGIN + CAPTION_HEIGHT
  const context = canvas.getContext('2d')!
  context.fillStyle = BACKGROUND
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(graph, (canvas.width - graph.width) / 2, MARGIN + CAPTION_HEIGHT)
  context.fillStyle = '#cbd5e1'
  context.font = '600 24px system-ui, sans-serif'
  context.fillText(caption, MARGIN, MARGIN)

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) throw new Error("L'image est trop grande pour être exportée")

  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}
