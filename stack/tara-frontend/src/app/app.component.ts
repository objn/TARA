import {
  ChangeDetectionStrategy,
  Component,
  CUSTOM_ELEMENTS_SCHEMA,
  ElementRef,
  viewChild,
} from '@angular/core';
import { beforeRender, NgtArgs } from 'angular-three';
import { NgtCanvas } from 'angular-three/dom';
import type { Mesh } from 'three';

@Component({
  selector: 'app-scene-graph',
  imports: [NgtArgs],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ngt-ambient-light [intensity]="1.5" />
    <ngt-point-light [position]="[4, 4, 5]" [intensity]="45" />
    <ngt-mesh #mesh [rotation]="[0.45, 0.55, 0]">
      <ngt-torus-knot-geometry *args="[0.95, 0.28, 180, 24]" />
      <ngt-mesh-standard-material
        color="#9b8cff"
        [metalness]="0.62"
        [roughness]="0.2"
      />
    </ngt-mesh>
  `,
})
class SceneGraphComponent {
  private readonly meshRef = viewChild.required<ElementRef<Mesh>>('mesh');
  private elapsed = 0;

  constructor() {
    beforeRender(({ delta }) => {
      const mesh = this.meshRef().nativeElement;
      this.elapsed += delta;
      mesh.rotation.y += delta * 0.65;
      mesh.rotation.x = 0.45 + Math.sin(this.elapsed * 0.7) * 0.12;
      mesh.position.y = Math.sin(this.elapsed) * 0.16;
    });
  }
}

@Component({
  selector: 'app-root',
  imports: [NgtCanvas, SceneGraphComponent],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="page-shell">
      <section class="intro" aria-label="Tara introduction">
        <p class="eyebrow">TARA · DIGITAL EXPERIENCE</p>
        <h1>Build something<br /><span>out of this world.</span></h1>
        <p class="description">
          A new space for ideas, connected systems, and experiences in three dimensions.
        </p>
        <a class="explore-link" href="#experience">
          <span>Explore the experience</span>
          <span aria-hidden="true">↗</span>
        </a>
      </section>

      <section class="scene-panel" id="experience" aria-label="Interactive 3D scene">
        <div class="scene-label"><span class="status-dot"></span> REAL-TIME SCENE</div>
        <ngt-canvas [camera]="{ position: [0, 0, 5], fov: 45 }">
          <ng-template canvasContent>
            <app-scene-graph />
          </ng-template>
        </ngt-canvas>
        <div class="scene-caption">A small glimpse of what’s possible</div>
      </section>

      <footer class="page-footer">
        <span>TARA BACKEND · FRONTEND STARTER</span>
        <span>ANGULAR THREE V4</span>
      </footer>
    </main>
  `,
  styles: `
    :host { display: block; min-height: 100vh; }
    .page-shell {
      position: relative;
      display: grid;
      grid-template-columns: minmax(300px, 0.8fr) minmax(420px, 1.2fr);
      align-items: center;
      gap: clamp(2rem, 7vw, 8rem);
      min-height: 100vh;
      max-width: 1440px;
      margin: 0 auto;
      padding: clamp(2rem, 6vw, 6rem);
      overflow: hidden;
    }
    .page-shell::before {
      position: absolute;
      z-index: -1;
      top: 12%;
      right: -15rem;
      width: 38rem;
      height: 38rem;
      border-radius: 50%;
      background: #6455d9;
      content: '';
      filter: blur(180px);
      opacity: 0.16;
    }
    .intro { max-width: 35rem; }
    .eyebrow, .page-footer, .scene-label {
      color: #aaa9bb;
      font-size: 0.7rem;
      font-weight: 650;
      letter-spacing: 0.16em;
    }
    h1 {
      margin: 1.5rem 0;
      font-size: clamp(3.25rem, 6.2vw, 6.5rem);
      font-weight: 560;
      letter-spacing: -0.075em;
      line-height: 0.98;
    }
    h1 span { color: #a49aff; }
    .description {
      max-width: 27rem;
      color: #aaa9bb;
      font-size: 1.05rem;
      line-height: 1.7;
    }
    .explore-link {
      display: inline-flex;
      align-items: center;
      gap: 2rem;
      margin-top: 2rem;
      padding: 0.95rem 1.2rem;
      border: 1px solid #444352;
      border-radius: 999px;
      color: #f5f4ff;
      font-size: 0.9rem;
      text-decoration: none;
      transition: border-color 160ms ease, background 160ms ease;
    }
    .explore-link:hover { border-color: #a49aff; background: #a49aff1a; }
    .scene-panel {
      position: relative;
      min-height: min(68vh, 660px);
      overflow: hidden;
      border: 1px solid #ffffff18;
      border-radius: 1.5rem;
      background: radial-gradient(ellipse at 50% 45%, #26233e 0, #15151d 48%, #101216 100%);
      box-shadow: 0 2rem 8rem #00000055;
    }
    ngt-canvas { display: block; width: 100%; height: min(68vh, 660px); min-height: 420px; }
    .scene-label, .scene-caption { position: absolute; z-index: 1; pointer-events: none; }
    .scene-label { top: 1.5rem; left: 1.5rem; display: flex; align-items: center; gap: 0.6rem; }
    .status-dot { width: 0.45rem; height: 0.45rem; border-radius: 50%; background: #75e0b0; box-shadow: 0 0 1rem #75e0b0aa; }
    .scene-caption { right: 1.5rem; bottom: 1.5rem; color: #aaa9bb; font-size: 0.8rem; }
    .page-footer { position: absolute; right: clamp(2rem, 6vw, 6rem); bottom: 1.5rem; left: clamp(2rem, 6vw, 6rem); display: flex; justify-content: space-between; font-size: 0.6rem; }
    @media (max-width: 850px) {
      .page-shell { grid-template-columns: 1fr; gap: 3rem; padding-bottom: 5rem; }
      .scene-panel, ngt-canvas { min-height: 480px; height: 58vh; }
      .page-footer { position: static; grid-column: 1; margin-top: 1rem; }
    }
    @media (max-width: 520px) {
      .page-shell { padding: 2rem 1.25rem 1.5rem; }
      .scene-panel, ngt-canvas { min-height: 380px; height: 48vh; }
      .page-footer { font-size: 0.5rem; }
    }
  `,
})
export class AppComponent {}
