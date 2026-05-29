// <maxgen-photo> — smart photo element.
// Picks primary photo, auto-crops to face_bounding_box when present,
// falls back to silhouette when no photo, lazy-loads thumbnails.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce } from './_base.js';

class MaxgenPhoto extends MaxgenElement {
  static properties = {
    // Accept either a full MaxPerson (.photo_assertions[]) or a single photo object.
    person: { type: Object },
    photo:  { type: Object },
    size:   { type: String },  // 'sm' 32, 'md' 64, 'lg' 128, 'xl' 200
    shape:  { type: String },  // 'circle' (default) | 'square'
  };
  constructor() {
    super();
    this.person = null;
    this.photo = null;
    this.size = 'md';
    this.shape = 'circle';
  }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; vertical-align: middle; }
    .frame {
      display: inline-block;
      background: linear-gradient(135deg, #efeae0, #d8d2c4);
      overflow: hidden;
      position: relative;
      flex-shrink: 0;
    }
    .frame.circle { border-radius: 50%; }
    .frame.square { border-radius: var(--radius-lg, 12px); }
    .sm { width: 32px;  height: 32px;  }
    .md { width: 64px;  height: 64px;  }
    .lg { width: 128px; height: 128px; }
    .xl { width: 200px; height: 200px; }
    img {
      width: 100%; height: 100%; object-fit: cover;
      display: block;
    }
    .silhouette {
      width: 100%; height: 100%;
      display: flex; align-items: center; justify-content: center;
      color: var(--muted, #6b6458);
      opacity: 0.6;
    }
    .silhouette svg { width: 60%; height: 60%; }
  `];

  _pickPhoto() {
    if (this.photo) return this.photo;
    if (!this.person || !Array.isArray(this.person.photo_assertions)) return null;
    const photos = this.person.photo_assertions.filter(p => p.url);
    if (!photos.length) return null;
    // Prefer is_primary, then highest confidence, then most recent.
    const primary = photos.find(p => p.is_primary);
    if (primary) return primary;
    return photos.slice().sort((a, b) => {
      const dc = (b.confidence || 0) - (a.confidence || 0);
      if (dc !== 0) return dc;
      return new Date(b.asserted_at || 0) - new Date(a.asserted_at || 0);
    })[0];
  }

  _faceCropStyle(p) {
    if (!p || !p.face_bounding_box) return '';
    const fb = p.face_bounding_box;
    // Use CSS object-position + a transform to crop on the face.
    // For simplicity here, set object-position based on face center.
    const cx = (fb.x + fb.width / 2) * 100;
    const cy = (fb.y + fb.height / 2) * 100;
    return `object-position: ${cx}% ${cy}%;`;
  }

  render() {
    const p = this._pickPhoto();
    const sz = ['sm','md','lg','xl'].includes(this.size) ? this.size : 'md';
    const shape = this.shape === 'square' ? 'square' : 'circle';
    const cls = `frame ${shape} ${sz}`;

    if (!p) {
      // Silhouette fallback — never empty.
      return html`
        <div class="${cls}"
             role="img"
             aria-label="No photo available">
          <div class="silhouette">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path fill="currentColor" d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm0 2c-3.3 0-10 1.7-10 5v3h20v-3c0-3.3-6.7-5-10-5z"/>
            </svg>
          </div>
        </div>
      `;
    }

    const src = p.thumbnail_url || p.url;
    const style = this._faceCropStyle(p);
    return html`
      <div class="${cls}">
        <img src="${src}"
             alt="${p.alt_text || 'Photograph'}"
             loading="lazy"
             style="${style}">
      </div>
    `;
  }
}
defineOnce('maxgen-photo', MaxgenPhoto);
