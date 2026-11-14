import {
  ChangeDetectionStrategy,
  Component,
  CUSTOM_ELEMENTS_SCHEMA,
  ElementRef,
  signal,
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
    @if (page() === 'welcome') {
      <main class="welcome-page">
        <header class="welcome-top"><a class="brand" href="#welcome"><span class="brand-mark">T</span><span>TARA</span></a><button class="login-top" type="button" (click)="goToLogin()">Sign in <span aria-hidden="true">↗</span></button></header>
        <section class="welcome-content" id="welcome"><div class="welcome-copy"><p class="eyebrow">TARA · DIGITAL EXPERIENCE</p><h1>A new space<br /><span>for your ideas.</span></h1><p class="description">Connect ideas, systems, and digital experiences in one place.</p><button class="welcome-cta" type="button" (click)="goToLogin()">Get started <span aria-hidden="true">↗</span></button><p class="welcome-note">Sign in to access your workspace.</p></div><div class="welcome-art" aria-hidden="true"><div class="art-orbit orbit-one"></div><div class="art-orbit orbit-two"></div><div class="art-core">T</div><span class="art-star star-one">✦</span><span class="art-star star-two">✧</span><span class="art-caption">IDEAS IN MOTION</span></div></section>
        <footer class="welcome-footer"><span>© 2026 TARA SPACE</span><span>MAKE ROOM FOR WHAT’S NEXT</span></footer>
      </main>
    } @else if (page() === 'login') {
      <main class="login-page"><header class="welcome-top"><a class="brand" href="#welcome" (click)="goToWelcome()"><span class="brand-mark">T</span><span>TARA</span></a><button class="back-link" type="button" (click)="goToWelcome()">← Back to home</button></header><section class="login-content"><div class="login-card"><div class="login-symbol">T</div><p class="eyebrow">WELCOME BACK</p><h1>Sign in</h1><p class="login-subtitle">Sign in to continue to your Tara workspace</p><form (submit)="signIn($event)"><label for="email">Email</label><input id="email" type="email" placeholder="name@example.com" autocomplete="email" required /><label for="password">Password</label><input id="password" type="password" placeholder="Enter your password" autocomplete="current-password" required /><div class="login-options"><label class="remember"><input type="checkbox" /> Remember me</label><a href="#forgot" (click)="$event.preventDefault()">Forgot password?</a></div><button class="submit-login" type="submit">Sign in <span aria-hidden="true">→</span></button></form><p class="mock-note">Mockup mode · Enter any details to continue</p></div></section></main>
    } @else {
    <div class="app-layout" [class.sidebar-collapsed]="sidebarCollapsed()">
      <header class="top-bar">
        <a class="brand" href="#home" aria-label="Tara home"><span class="brand-mark">T</span><span>TARA</span></a>
        <nav class="top-links" aria-label="Main navigation"><a class="top-link active" href="#home">Overview</a><a class="top-link" href="#experience">Experience</a></nav>
        <button class="top-action" type="button" (click)="signOut()">Sign out <span aria-hidden="true">↗</span></button>
      </header>
      <aside class="side-bar" aria-label="Workspace navigation">
        <button class="sidebar-toggle" type="button" (click)="toggleSidebar()" [attr.aria-expanded]="!sidebarCollapsed()" [attr.aria-label]="sidebarCollapsed() ? 'Expand sidebar' : 'Collapse sidebar'"><span aria-hidden="true">{{ sidebarCollapsed() ? '›' : '‹' }}</span></button>
        <div class="side-menu-group">
          <p class="side-heading">OVERVIEW</p>
          <nav class="side-nav">
            <button class="side-link" [class.selected]="section() === 'dashboard'" type="button" (click)="setSection('dashboard')"><span class="nav-icon">⌂</span><span>Dashboard</span></button>
            <button class="side-link" [class.selected]="section() === 'activity'" type="button" (click)="setSection('activity')"><span class="nav-icon">◷</span><span>TARA Activity</span></button>
            <button class="side-link" [class.selected]="section() === 'service-health'" type="button" (click)="setSection('service-health')"><span class="nav-icon">◉</span><span>Service Health</span></button>
          </nav>
        </div>
        <div class="side-bottom"><span class="avatar">T</span><span class="profile-copy"><strong>Tara Space</strong><small>Personal workspace</small></span><span class="profile-more">···</span></div>
      </aside>
    @if (section() === 'service-health') {
    <main class="dashboard service-page" id="service-health">
      <header class="dashboard-heading"><div><p class="eyebrow">AGENTIC SYSTEM / MONITORING</p><h1>Service Health</h1><p class="dashboard-subtitle">Monitor readiness and availability across your services.</p></div><div class="live-status"><span class="status-dot"></span> Live monitoring <span class="updated-at">Updated just now</span></div></header>
      <section class="service-toolbar" aria-label="Service controls"><label class="service-search"><span aria-hidden="true">⌕</span><input type="search" placeholder="Search services..." [value]="serviceSearch()" (input)="setServiceSearch($event)" aria-label="Search services by any field" /></label><label class="filter-control"><span>Filter</span><select [value]="serviceStatusFilter()" (change)="setServiceStatusFilter($event)" aria-label="Filter services by status"><option value="All">All statuses</option><option value="Healthy">Healthy</option><option value="Degraded">Degraded</option><option value="Down">Down</option></select></label><span class="result-count">{{ filteredServices().length }} services</span></section>
      <section class="panel service-table-panel"><div class="service-table-scroll"><table class="service-table"><thead><tr><th>No.</th><th>Name</th><th>Address</th><th>Ready%</th><th>Status</th></tr></thead><tbody>
        @for (service of filteredServices(); track service.no) {
          <tr><td class="service-number">{{ service.no }}</td><td><span class="service-name"><span class="service-type-icon">{{ service.icon }}</span>{{ service.name }}</span></td><td><code>{{ service.address }}</code></td><td><div class="ready-cell"><div class="ready-track"><i [style.width.%]="service.ready"></i></div><span>{{ service.ready }}%</span></div></td><td><span class="service-status" [class.healthy]="service.status === 'Healthy'" [class.degraded]="service.status === 'Degraded'" [class.down]="service.status === 'Down'"><i></i>{{ service.status }}</span></td></tr>
        } @empty {
          <tr><td class="empty-services" colspan="5">No services match your search.</td></tr>
        }
      </tbody></table></div><footer class="table-footer"><span>Showing {{ filteredServices().length }} of {{ services.length }} services</span><span>Readiness window · last 5 minutes</span></footer></section>
    </main>
    } @else if (section() === 'activity') {
    <main class="dashboard activity-page" id="activity">
      <header class="dashboard-heading"><div><p class="eyebrow">AGENTIC SYSTEM / MONITORING</p><h1>TARA Activity</h1><p class="dashboard-subtitle">Review what your agents are doing and the actions they have taken.</p></div><div class="live-status"><span class="status-dot"></span> Activity stream <span class="updated-at">Live</span></div></header>
      <div class="activity-tabs" role="tablist" aria-label="Activity views"><button type="button" role="tab" [attr.aria-selected]="activityTab() === 'agents'" [class.active]="activityTab() === 'agents'" (click)="setActivityTab('agents')">Agents <span>4</span></button><button type="button" role="tab" [attr.aria-selected]="activityTab() === 'log'" [class.active]="activityTab() === 'log'" (click)="setActivityTab('log')">Log <span>24</span></button></div>
      <section class="service-toolbar activity-toolbar" aria-label="Activity controls"><label class="service-search"><span aria-hidden="true">⌕</span><input type="search" [placeholder]="activityTab() === 'agents' ? 'Search agents, actions, or status...' : 'Search logs, agents, actions, or results...'" [value]="activitySearch()" (input)="setActivitySearch($event)" aria-label="Search activity by any field" /></label><label class="filter-control"><span>Filter</span><select [value]="activityFilter()" (change)="setActivityFilter($event)" aria-label="Filter activity"><option value="All">{{ activityTab() === 'agents' ? 'All statuses' : 'All actions' }}</option>@if (activityTab() === 'agents') {<option value="Running">Running</option><option value="Waiting">Waiting</option><option value="Completed">Completed</option>} @else {<option value="Tool call">Tool call</option><option value="Reasoning">Reasoning</option><option value="Message">Message</option><option value="Output">Output</option>}</select></label><span class="result-count">{{ activityResultCount() }} results</span></section>
      @if (activityTab() === 'agents') {
        <section class="panel service-table-panel"><div class="service-table-scroll"><table class="service-table activity-table"><thead><tr><th>Agent</th><th>Current action</th><th>Started</th><th>Duration</th><th>Status</th></tr></thead><tbody>
          <tr [hidden]="!activityRowMatches('Research Agent Analyzing market signals 11:02:18 03:42 Running', 'Running')"><td><span class="service-name"><span class="agent-avatar agent-purple">R</span>Research Agent</span></td><td>Analyzing market signals</td><td>11:02:18</td><td>03:42</td><td><span class="state-chip running">Running</span></td></tr>
          <tr [hidden]="!activityRowMatches('Code Assistant Reviewing pull request 284 11:04:42 01:18 Running', 'Running')"><td><span class="service-name"><span class="agent-avatar agent-blue">C</span>Code Assistant</span></td><td>Reviewing pull request #284</td><td>11:04:42</td><td>01:18</td><td><span class="state-chip running">Running</span></td></tr>
          <tr [hidden]="!activityRowMatches('Data Analyst Waiting for user input 10:58:06 Waiting', 'Waiting')"><td><span class="service-name"><span class="agent-avatar agent-green">D</span>Data Analyst</span></td><td>Waiting for user input</td><td>10:58:06</td><td>—</td><td><span class="state-chip waiting">Waiting</span></td></tr>
          <tr [hidden]="!activityRowMatches('Writing Agent Generated weekly summary 10:56:32 00:56 Completed', 'Completed')"><td><span class="service-name"><span class="agent-avatar agent-orange">W</span>Writing Agent</span></td><td>Generated weekly summary</td><td>10:56:32</td><td>00:56</td><td><span class="state-chip done">Completed</span></td></tr>
        </tbody></table></div><footer class="table-footer"><span>4 agents in this workspace</span><span>Auto-refresh · 10 seconds</span></footer></section>
      } @else {
        <section class="panel service-table-panel"><div class="service-table-scroll"><table class="service-table activity-table log-table"><thead><tr><th>Time</th><th>Agent</th><th>Action</th><th>Details</th><th>Result</th></tr></thead><tbody>
          <tr [hidden]="!activityRowMatches('11:06:42 Research Agent Tool call web_search queried market trends Success', 'Tool call')"><td class="log-time">11:06:42</td><td>Research Agent</td><td><span class="action-label"><i class="action-tool"></i>Tool call</span></td><td>web_search · queried market trends</td><td><span class="service-status healthy"><i></i>Success</span></td></tr>
          <tr [hidden]="!activityRowMatches('11:05:18 Code Assistant Reasoning Reviewed 8 files in pull request 284 Completed', 'Reasoning')"><td class="log-time">11:05:18</td><td>Code Assistant</td><td><span class="action-label"><i class="action-reason"></i>Reasoning</span></td><td>Reviewed 8 files in pull request #284</td><td><span class="service-status healthy"><i></i>Completed</span></td></tr>
          <tr [hidden]="!activityRowMatches('11:04:53 Research Agent Message Saved 12 sources to research notes Success', 'Message')"><td class="log-time">11:04:53</td><td>Research Agent</td><td><span class="action-label"><i class="action-message"></i>Message</span></td><td>Saved 12 sources to research notes</td><td><span class="service-status healthy"><i></i>Success</span></td></tr>
          <tr [hidden]="!activityRowMatches('11:03:10 Data Analyst Tool call sql_query daily active users Retrying', 'Tool call')"><td class="log-time">11:03:10</td><td>Data Analyst</td><td><span class="action-label"><i class="action-tool"></i>Tool call</span></td><td>sql_query · daily active users</td><td><span class="service-status degraded"><i></i>Retrying</span></td></tr>
          <tr [hidden]="!activityRowMatches('11:02:18 Writing Agent Output Weekly summary draft generated Completed', 'Output')"><td class="log-time">11:02:18</td><td>Writing Agent</td><td><span class="action-label"><i class="action-message"></i>Output</span></td><td>Weekly summary draft generated</td><td><span class="service-status healthy"><i></i>Completed</span></td></tr>
          <tr [hidden]="!activityRowMatches('11:01:44 Code Assistant Tool call github fetched pull request 284 Success', 'Tool call')"><td class="log-time">11:01:44</td><td>Code Assistant</td><td><span class="action-label"><i class="action-tool"></i>Tool call</span></td><td>github · fetched pull request #284</td><td><span class="service-status healthy"><i></i>Success</span></td></tr>
          <tr [hidden]="!activityRowMatches('10:59:31 Research Agent Reasoning Comparing findings across 12 sources Completed', 'Reasoning')"><td class="log-time">10:59:31</td><td>Research Agent</td><td><span class="action-label"><i class="action-reason"></i>Reasoning</span></td><td>Comparing findings across 12 sources</td><td><span class="service-status healthy"><i></i>Completed</span></td></tr>
        </tbody></table></div><footer class="table-footer"><span>Showing 7 of 24 events</span><span>Newest first · All agents</span></footer></section>
      }
    </main>
    } @else {
    <main class="dashboard" id="home">
      <header class="dashboard-heading"><div><p class="eyebrow">AGENTIC SYSTEM / OVERVIEW</p><h1>Dashboard</h1><p class="dashboard-subtitle">Monitor agents, workflows, and system health in real time.</p></div><div class="live-status"><span class="status-dot"></span> All systems operational <span class="updated-at">Updated just now</span></div></header>

      <section class="metric-grid" aria-label="System overview">
        <article class="metric-card"><div class="metric-top"><span>Active agents</span><span class="metric-icon violet">◈</span></div><strong>12 <small>/ 16</small></strong><div class="metric-foot"><span class="mini-bars"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span><span>+2 in the last hour</span></div></article>
        <article class="metric-card"><div class="metric-top"><span>Running tasks</span><span class="metric-icon blue">⌁</span></div><strong>38</strong><div class="metric-foot"><span class="trend-up">↗ 12%</span><span>vs. previous hour</span></div></article>
        <article class="metric-card"><div class="metric-top"><span>Queue depth</span><span class="metric-icon amber">≋</span></div><strong>07</strong><div class="metric-foot"><span class="queue-pill">Healthy</span><span>Oldest task · 14 sec</span></div></article>
        <article class="metric-card"><div class="metric-top"><span>Success rate</span><span class="metric-icon green">✓</span></div><strong>98.6<small>%</small></strong><div class="metric-foot"><span class="trend-up">+0.8%</span><span>over the last 24 hours</span></div></article>
      </section>

      <section class="monitor-grid">
        <article class="panel activity-panel"><div class="panel-heading"><div><h2>Agent activity</h2><p>Task throughput across your agents</p></div><button class="period-select" type="button">Last 60 min <span>⌄</span></button></div><div class="chart-legend"><span><i class="legend-dot violet-dot"></i>Completed</span><span><i class="legend-dot green-dot"></i>In progress</span></div><div class="activity-chart" aria-label="Agent activity line chart"><div class="chart-y-labels"><span>40</span><span>30</span><span>20</span><span>10</span><span>0</span></div><div class="chart-plot"><div class="chart-grid-lines"><i></i><i></i><i></i><i></i><i></i></div><svg viewBox="0 0 700 200" preserveAspectRatio="none" aria-hidden="true"><polyline class="chart-line completed-line" points="0,155 35,145 65,158 95,123 130,138 160,95 190,110 220,78 255,100 285,84 320,118 350,88 385,96 420,62 455,85 490,70 525,90 560,55 595,74 630,50 665,64 700,45"/><polyline class="chart-line progress-line" points="0,177 35,168 65,173 95,160 130,165 160,145 190,154 220,137 255,150 285,134 320,148 350,128 385,141 420,121 455,133 490,120 525,138 560,112 595,125 630,106 665,118 700,101"/></svg><div class="chart-x-labels"><span>10:00</span><span>10:15</span><span>10:30</span><span>10:45</span><span>11:00</span></div></div></div></article>

        <article class="panel agent-panel"><div class="panel-heading"><div><h2>Agent status</h2><p>Live runtime overview</p></div><button class="text-action" type="button">View all <span>→</span></button></div><div class="agent-list"><div class="agent-row"><span class="agent-avatar agent-purple">R</span><span class="agent-info"><strong>Research Agent</strong><small>Analyzing market signals</small></span><span class="agent-runtime">03:42</span><span class="state-chip running">Running</span></div><div class="agent-row"><span class="agent-avatar agent-blue">C</span><span class="agent-info"><strong>Code Assistant</strong><small>Reviewing pull request</small></span><span class="agent-runtime">01:18</span><span class="state-chip running">Running</span></div><div class="agent-row"><span class="agent-avatar agent-green">D</span><span class="agent-info"><strong>Data Analyst</strong><small>Waiting for input</small></span><span class="agent-runtime">—</span><span class="state-chip waiting">Waiting</span></div><div class="agent-row"><span class="agent-avatar agent-orange">W</span><span class="agent-info"><strong>Writing Agent</strong><small>Summary generated</small></span><span class="agent-runtime">00:56</span><span class="state-chip done">Completed</span></div></div></article>
      </section>

      <section class="lower-grid">
        <article class="panel resource-panel"><div class="panel-heading"><div><h2>System resources</h2><p>Runtime capacity across the agent fleet</p></div><span class="resource-period">LIVE</span></div><div class="resource-list"><div class="resource-row"><div class="resource-label"><span>CPU utilization</span><strong>42%</strong></div><div class="progress-track"><i class="cpu-progress"></i></div></div><div class="resource-row"><div class="resource-label"><span>Memory</span><strong>6.4 <small>/ 16 GB</small></strong></div><div class="progress-track"><i class="memory-progress"></i></div></div><div class="resource-row"><div class="resource-label"><span>Tool calls / min</span><strong>126</strong></div><div class="sparkline"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div></div></article>
        <article class="panel events-panel"><div class="panel-heading"><div><h2>Recent events</h2><p>Latest system activity</p></div><button class="text-action" type="button">Activity log <span>→</span></button></div><div class="event-list"><div class="event-row"><span class="event-mark event-success">✓</span><span><strong>Workflow completed</strong><small>Research pipeline · 2 min ago</small></span></div><div class="event-row"><span class="event-mark event-info">↗</span><span><strong>Agent started</strong><small>Code Assistant · 5 min ago</small></span></div><div class="event-row"><span class="event-mark event-warning">!</span><span><strong>Tool retry successful</strong><small>Web search · 8 min ago</small></span></div></div></article>
      </section>
    </main>
    }
    </div>
    }
  `,
  styles: `
    :host { display: block; min-height: 100vh; }
    .welcome-page,.login-page { position: relative; min-height: 100vh; overflow: hidden; background: radial-gradient(ellipse at 75% 50%,#211d39 0,#14151d 42%,#101216 76%); }
    .welcome-top { position: absolute; z-index: 2; inset: 0 0 auto; height: 5.5rem; display: flex; align-items: center; justify-content: space-between; padding: 0 clamp(1.5rem,6vw,6rem); border-bottom: 1px solid #ffffff0c; }
    .login-top,.welcome-cta,.top-action { display: inline-flex; align-items: center; gap: 1.5rem; padding: .8rem 1.15rem; border: 1px solid #a49aff70; border-radius: .75rem; background: #a49aff19; color: #f5f4ff; font: inherit; font-size: .85rem; cursor: pointer; transition: background 160ms ease,border-color 160ms ease; }
    .login-top:hover,.welcome-cta:hover,.top-action:hover { border-color: #b6adff; background: #a49aff32; }
    .welcome-content { display: grid; grid-template-columns: 1fr 1fr; align-items: center; gap: 2rem; width: min(1300px,100%); min-height: calc(100vh - 6rem); margin: auto; padding: 7rem clamp(1.5rem,8vw,8rem) 5rem; }
    .welcome-copy { position: relative; z-index: 1; max-width: 38rem; }.welcome-copy h1 { margin: 1.4rem 0; font-size: clamp(3rem,6vw,6rem); font-weight: 560; letter-spacing: -.07em; line-height: 1.13; }.welcome-copy h1 span { color: #a49aff; }
    .welcome-copy .description { max-width: 29rem; margin-bottom: 2rem; }.welcome-note { margin-top: 1rem; color: #777684; font-size: .75rem; }
    .welcome-art { position: relative; display: grid; min-height: 32rem; place-items: center; isolation: isolate; }.welcome-art::before { position: absolute; z-index: -1; width: 20rem; height: 20rem; border-radius: 50%; background: #7868eb; content: ''; filter: blur(150px); opacity: .25; }
    .art-orbit { position: absolute; width: min(34vw,27rem); height: min(34vw,27rem); border: 1px solid #b1a8ff36; border-radius: 50%; transform: rotate(-25deg) scaleY(.42); box-shadow: 0 0 3rem #7868eb16; }.orbit-two { width: min(29vw,23rem); height: min(29vw,23rem); transform: rotate(55deg) scaleY(.5); border-color: #75e0b044; }
    .art-core { display: grid; width: 9rem; height: 9rem; place-items: center; border: 1px solid #ffffff35; border-radius: 2.5rem; background: linear-gradient(145deg,#a49aff,#5444bf); box-shadow: 0 1.5rem 6rem #7565e566,inset 0 1px #ffffff80; color: #171522; font-size: 4rem; font-weight: 700; transform: rotate(-10deg); }
    .art-star { position: absolute; color: #c8c1ff; }.star-one { top: 20%; right: 17%; font-size: 2rem; }.star-two { bottom: 22%; left: 14%; color: #75e0b0; font-size: 1.5rem; }.art-caption { position: absolute; right: 3%; bottom: 18%; color: #aaa9bb; font-size: .6rem; letter-spacing: .22em; }
    .welcome-footer { position: absolute; inset: auto clamp(1.5rem,6vw,6rem) 1.5rem; display: flex; justify-content: space-between; color: #747380; font-size: .58rem; letter-spacing: .15em; }
    .login-content { display: grid; min-height: 100vh; place-items: center; padding: 7rem 1.25rem 3rem; }.login-card { width: min(100%,27rem); padding: 2.5rem; border: 1px solid #ffffff19; border-radius: 1.25rem; background: #171820e8; box-shadow: 0 2rem 7rem #0006; }
    .login-symbol { display: grid; width: 2.8rem; height: 2.8rem; margin-bottom: 1.5rem; place-items: center; border-radius: .8rem; background: linear-gradient(145deg,#a49aff,#6655dc); color: #14121e; font-size: 1.35rem; font-weight: 700; }
    .login-card h1 { margin: .5rem 0; font-size: 2rem; letter-spacing: -.05em; }.login-subtitle { margin: 0 0 1.8rem; color: #aaa9bb; font-size: .87rem; }.login-card form { display: grid; gap: .65rem; }.login-card form > label { margin-top: .55rem; color: #d4d2e0; font-size: .78rem; }
    .login-card input[type=email],.login-card input[type=password] { width: 100%; padding: .85rem .9rem; border: 1px solid #ffffff20; border-radius: .65rem; outline: none; background: #101116; color: #f5f4ff; font: inherit; font-size: .85rem; }.login-card input:focus { border-color: #a49aff; box-shadow: 0 0 0 3px #a49aff20; }
    .login-options { display: flex; justify-content: space-between; align-items: center; margin: .45rem 0 1rem; color: #a4a3b1; font-size: .75rem; }.remember { display: flex; align-items: center; gap: .4rem; }.remember input { accent-color: #9587f5; }.login-options a { color: #b6adff; text-decoration: none; }
    .submit-login { display: flex; justify-content: space-between; align-items: center; padding: .9rem 1rem; border: 0; border-radius: .65rem; background: #9183ef; color: #171522; font: inherit; font-size: .88rem; font-weight: 650; cursor: pointer; }.submit-login:hover { background: #a49aff; }.mock-note { margin: 1.2rem 0 0; color: #777684; font-size: .68rem; text-align: center; }.back-link { border: 0; background: transparent; color: #aaa9bb; font: inherit; font-size: .82rem; cursor: pointer; }.back-link:hover { color: #f5f4ff; }
    .app-layout { min-height: 100vh; padding: 4.25rem 0 0 15.5rem; transition: padding-left 200ms ease; }
    .app-layout.sidebar-collapsed { padding-left: 4.5rem; }
    .top-bar { position: fixed; z-index: 5; inset: 0 0 auto; height: 4.25rem; display: flex; align-items: center; gap: 3rem; padding: 0 2.5rem; border-bottom: 1px solid #ffffff12; background: #101216ef; backdrop-filter: blur(18px); }
    .brand { display: inline-flex; align-items: center; gap: .75rem; min-width: 12rem; color: #f5f4ff; font-size: .8rem; font-weight: 750; letter-spacing: .16em; text-decoration: none; }
    .brand-mark { display: grid; width: 1.8rem; height: 1.8rem; place-items: center; border-radius: .55rem; background: linear-gradient(145deg,#a49aff,#6655dc); color: #14121e; font-size: .95rem; letter-spacing: 0; }
    .top-links { display: flex; align-items: center; gap: 1.8rem; height: 100%; }
    .top-link { display: grid; align-items: center; height: 100%; border-bottom: 2px solid transparent; color: #898897; font-size: .83rem; text-decoration: none; }
    .top-link:hover,.top-link.active { color: #f5f4ff; }.top-link.active { border-bottom-color: #a49aff; }
    .top-action { gap: 1.5rem; margin-left: auto; text-decoration: none; }
    .side-bar { position: fixed; z-index: 4; inset: 4.25rem auto 0 0; display: flex; flex-direction: column; width: 15.5rem; padding: 1rem; border-right: 1px solid #ffffff12; background: #121319; transition: width 200ms ease; }
    .side-menu-group { flex: 0 0 auto; margin-top: 0; }
    .sidebar-toggle { display: grid; flex: 0 0 2.6rem; place-items: center; width: 2.6rem; height: 2.6rem; align-self: flex-end; margin: 0 0 1.5rem; padding: 0; border: 1px solid #ffffff14; border-radius: .6rem; background: #ffffff06; color: #aaa9bb; font: inherit; cursor: pointer; }
    .sidebar-toggle:hover { border-color: #a49aff55; color: #f5f4ff; }.sidebar-toggle > span:first-child { display: grid; width: 100%; height: 100%; place-items: center; color: #b6adff; font-size: 1.35rem; line-height: 1; }
    .sidebar-collapsed .side-bar { width: 4.5rem; align-items: center; padding-inline: .45rem; }
    .sidebar-collapsed .side-heading,.sidebar-collapsed .side-link span:last-child,.sidebar-collapsed .profile-copy,.sidebar-collapsed .profile-more { display: none; }
    .sidebar-collapsed .sidebar-toggle { align-self: center; margin-bottom: 1.5rem; }.sidebar-collapsed .side-link { justify-content: center; width: 2.65rem; min-height: 2.65rem; margin-inline: auto; padding: 0; }.sidebar-collapsed .nav-icon { flex-basis: 1.5rem; width: 1.5rem; }
    .side-heading { margin: 0 0 1rem .65rem; color: #777684; font-size: .62rem; font-weight: 700; letter-spacing: .16em; }
    .side-nav { display: grid; gap: .35rem; min-width: 0; }.side-link { display: flex; flex: 0 0 auto; align-items: center; gap: .85rem; width: 100%; min-width: 0; min-height: 2.65rem; padding: .55rem .75rem; border: 0; border-radius: .65rem; background: transparent; color: #a4a3b1; font: inherit; font-size: .82rem; text-align: left; text-decoration: none; cursor: pointer; transition: color 160ms ease,background 160ms ease; }
    .side-link > span:last-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .side-link:hover { background: #ffffff09; color: #f5f4ff; }.side-link.selected { background: #a49aff19; color: #c3bcff; }
    .nav-icon { display: grid; flex: 0 0 1.5rem; width: 1.5rem; height: 1.5rem; place-items: center; color: #9694a7; font-size: 1.35rem; line-height: 1; }.selected .nav-icon { color: #b1a8ff; }
    .side-bottom { display: flex; flex: 0 0 auto; align-items: center; gap: .7rem; min-height: 3.25rem; margin-top: auto; padding: .9rem .5rem .25rem; border-top: 1px solid #ffffff12; overflow: hidden; }
    .avatar { display: grid; flex: 0 0 2rem; width: 2rem; height: 2rem; place-items: center; border-radius: 50%; background: #37334d; color: #c6beff; font-weight: 700; }
    .profile-copy { display: grid; flex: 1 1 auto; gap: .16rem; min-width: 0; overflow: hidden; white-space: nowrap; }.profile-copy strong,.profile-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.profile-copy strong { color: #e9e8f3; font-size: .73rem; font-weight: 600; }.profile-copy small { color: #858391; font-size: .63rem; }.profile-more { flex: 0 0 auto; margin-left: auto; color: #858391; letter-spacing: .08em; }
    .page-shell {
      position: relative;
      display: grid;
      grid-template-columns: minmax(300px, 0.8fr) minmax(420px, 1.2fr);
      align-items: center;
      gap: clamp(2rem, 7vw, 8rem);
      min-height: calc(100vh - 4.25rem);
      max-width: 1440px;
      margin: 0 auto;
      padding: clamp(2rem, 5vw, 5rem);
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
    .dashboard { display: grid; gap: 1.15rem; width: min(100%, 1600px); min-height: calc(100vh - 4.25rem); margin: 0 auto; padding: 1.6rem clamp(1.25rem,2.5vw,2.5rem) 1.5rem; color: #f5f4ff; }
    .dashboard-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }.dashboard-heading .eyebrow { margin: 0 0 .4rem; color: #9389e8; font-size: .62rem; }.dashboard-heading h1 { margin: 0; font-size: 1.65rem; font-weight: 620; letter-spacing: -.04em; line-height: 1.2; }.dashboard-subtitle { margin: .35rem 0 0; color: #8c8b9b; font-size: .78rem; }
    .live-status { display: flex; align-items: center; gap: .5rem; padding: .55rem .75rem; border: 1px solid #75e0b02a; border-radius: .65rem; background: #75e0b00b; color: #a8e8cb; font-size: .7rem; white-space: nowrap; }.live-status .status-dot { width: .4rem; height: .4rem; }.updated-at { margin-left: .35rem; padding-left: .65rem; border-left: 1px solid #ffffff18; color: #777684; }
    .metric-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: .85rem; }.metric-card,.panel { min-width: 0; border: 1px solid #ffffff12; border-radius: .8rem; background: linear-gradient(145deg,#171820,#14151b); box-shadow: 0 .6rem 2rem #00000012; }
    .metric-card { padding: .9rem 1rem .8rem; }.metric-top { display: flex; align-items: center; justify-content: space-between; color: #a09faf; font-size: .72rem; }.metric-icon { display: grid; width: 1.65rem; height: 1.65rem; place-items: center; border-radius: .5rem; font-size: .9rem; }.metric-icon.violet { background: #a49aff18; color: #b5aaff; }.metric-icon.blue { background: #74aaff18; color: #86b5ff; }.metric-icon.amber { background: #ffc46b18; color: #ffc46b; }.metric-icon.green { background: #75e0b018; color: #75e0b0; }
    .metric-card > strong { display: block; margin: .5rem 0 .4rem; color: #f4f3ff; font-size: 1.65rem; font-weight: 620; letter-spacing: -.045em; }.metric-card > strong small { color: #777684; font-size: .85rem; font-weight: 500; letter-spacing: 0; }.metric-foot { display: flex; align-items: center; gap: .5rem; color: #767583; font-size: .63rem; white-space: nowrap; }.trend-up { color: #75e0b0; }.queue-pill { padding: .15rem .4rem; border-radius: 999px; background: #75e0b014; color: #75e0b0; }.mini-bars { display: flex; align-items: end; gap: 2px; height: .8rem; }.mini-bars i { width: 3px; border-radius: 2px; background: #a49aff; }.mini-bars i:nth-child(1){height:35%}.mini-bars i:nth-child(2){height:60%}.mini-bars i:nth-child(3){height:46%}.mini-bars i:nth-child(4){height:85%}.mini-bars i:nth-child(5){height:55%}.mini-bars i:nth-child(6){height:100%}.mini-bars i:nth-child(7){height:72%}.mini-bars i:nth-child(8){height:90%}.mini-bars i:nth-child(9){height:100%}
    .monitor-grid,.lower-grid { display: grid; grid-template-columns: minmax(0,1.45fr) minmax(360px,1fr); gap: .85rem; }.lower-grid { grid-template-columns: minmax(0,1fr) minmax(360px,1fr); }.panel { padding: 1rem 1.05rem; }.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: .75rem; }.panel-heading h2 { margin: 0; color: #e9e8f3; font-size: .83rem; font-weight: 600; }.panel-heading p { margin: .25rem 0 0; color: #777684; font-size: .66rem; }
    .period-select { padding: .4rem .55rem; border: 1px solid #ffffff16; border-radius: .45rem; background: #ffffff05; color: #aaa9bb; font: inherit; font-size: .63rem; }.period-select span { margin-left: .3rem; color: #777684; }.text-action { border: 0; background: transparent; color: #aaa0ff; font: inherit; font-size: .65rem; white-space: nowrap; }.text-action span { margin-left: .3rem; }
    .chart-legend { display: flex; gap: .9rem; margin: .8rem 0 .3rem 2rem; color: #858391; font-size: .61rem; }.chart-legend span { display: flex; align-items: center; gap: .35rem; }.legend-dot { width: .42rem; height: .42rem; border-radius: 50%; }.violet-dot { background: #9b8cff; }.green-dot { background: #75e0b0; }
    .activity-chart { display: grid; grid-template-columns: 1.5rem minmax(0,1fr); height: 11rem; }.chart-y-labels { display: flex; flex-direction: column; justify-content: space-between; padding: .4rem .3rem 1.35rem 0; color: #656472; font-size: .56rem; text-align: right; }.chart-plot { position: relative; min-width: 0; margin: .3rem 0 1.25rem; }.chart-grid-lines { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: space-between; }.chart-grid-lines i { border-top: 1px solid #ffffff0b; }.chart-plot svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }.chart-line { fill: none; stroke-width: 2.6; vector-effect: non-scaling-stroke; }.completed-line { stroke: #9b8cff; }.progress-line { stroke: #75e0b0; opacity: .8; }.chart-x-labels { position: absolute; inset: auto 0 -1.25rem; display: flex; justify-content: space-between; color: #656472; font-size: .56rem; }
    .agent-list { display: grid; margin-top: .65rem; }.agent-row { display: grid; grid-template-columns: 2rem minmax(0,1fr) 2.6rem auto; align-items: center; gap: .6rem; min-height: 3.2rem; border-top: 1px solid #ffffff0b; }.agent-avatar { display: grid; width: 1.8rem; height: 1.8rem; place-items: center; border-radius: .55rem; font-size: .72rem; font-weight: 650; }.agent-purple { background: #a49aff1a; color: #b5aaff; }.agent-blue { background: #74aaff1a; color: #86b5ff; }.agent-green { background: #75e0b01a; color: #75e0b0; }.agent-orange { background: #ffc46b1a; color: #ffc46b; }.agent-info { display: grid; gap: .2rem; min-width: 0; }.agent-info strong { overflow: hidden; color: #dedde9; font-size: .68rem; font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }.agent-info small { overflow: hidden; color: #777684; font-size: .59rem; text-overflow: ellipsis; white-space: nowrap; }.agent-runtime { color: #8b8999; font-size: .6rem; font-variant-numeric: tabular-nums; }.state-chip { justify-self: end; padding: .23rem .42rem; border-radius: 999px; font-size: .55rem; white-space: nowrap; }.state-chip.running { background: #a49aff16; color: #b5aaff; }.state-chip.waiting { background: #ffc46b16; color: #ffc46b; }.state-chip.done { background: #75e0b016; color: #75e0b0; }
    .resource-period { color: #75e0b0; font-size: .58rem; letter-spacing: .14em; }.resource-list { display: grid; gap: .8rem; margin-top: 1rem; }.resource-row { display: grid; gap: .4rem; }.resource-label { display: flex; justify-content: space-between; color: #8d8c9a; font-size: .64rem; }.resource-label strong { color: #d8d6e5; font-size: .64rem; font-weight: 550; }.resource-label small { color: #777684; font-size: .58rem; font-weight: 400; }.progress-track { height: .38rem; overflow: hidden; border-radius: 999px; background: #ffffff0c; }.progress-track i { display: block; height: 100%; border-radius: inherit; }.cpu-progress { width: 42%; background: linear-gradient(90deg,#7769de,#a49aff); }.memory-progress { width: 40%; background: linear-gradient(90deg,#477fbf,#79b4ff); }.sparkline { display: flex; align-items: end; gap: 3px; height: 1.3rem; padding-top: .15rem; }.sparkline i { flex: 1; border-radius: 2px 2px 0 0; background: #75e0b0a0; }.sparkline i:nth-child(4n+1){height:35%}.sparkline i:nth-child(4n+2){height:60%}.sparkline i:nth-child(4n+3){height:45%}.sparkline i:nth-child(4n){height:85%}
    .event-list { display: grid; margin-top: .65rem; }.event-row { display: flex; align-items: center; gap: .65rem; min-height: 2.5rem; border-top: 1px solid #ffffff0b; }.event-mark { display: grid; flex: 0 0 1.45rem; width: 1.45rem; height: 1.45rem; place-items: center; border-radius: .45rem; font-size: .7rem; }.event-success { background: #75e0b014; color: #75e0b0; }.event-info { background: #a49aff14; color: #a49aff; }.event-warning { background: #ffc46b14; color: #ffc46b; }.event-row > span:last-child { display: grid; gap: .16rem; }.event-row strong { color: #d8d6e5; font-size: .64rem; font-weight: 550; }.event-row small { color: #777684; font-size: .58rem; }
    .service-toolbar { display: flex; align-items: center; gap: .65rem; }.service-search { display: flex; align-items: center; gap: .6rem; width: min(100%,24rem); height: 2.55rem; padding: 0 .8rem; border: 1px solid #ffffff16; border-radius: .6rem; background: #171820; color: #858391; }.service-search > span { font-size: 1.2rem; line-height: 1; }.service-search input { width: 100%; border: 0; outline: 0; background: transparent; color: #f5f4ff; font: inherit; font-size: .75rem; }.service-search input::placeholder { color: #777684; }.filter-control { display: flex; align-items: center; gap: .5rem; height: 2.55rem; padding: 0 .75rem; border: 1px solid #ffffff16; border-radius: .6rem; background: #171820; color: #858391; font-size: .7rem; }.filter-control select { border: 0; outline: 0; background: transparent; color: #dedde9; font: inherit; font-size: .7rem; cursor: pointer; }.filter-control option { background: #171820; }.result-count { margin-left: auto; color: #777684; font-size: .68rem; }
    .activity-tabs { display: flex; gap: 1.2rem; border-bottom: 1px solid #ffffff12; }.activity-tabs button { position: relative; display: inline-flex; align-items: center; gap: .45rem; padding: .7rem .15rem .8rem; border: 0; background: transparent; color: #858391; font: inherit; font-size: .75rem; cursor: pointer; }.activity-tabs button.active { color: #e7e5f3; }.activity-tabs button.active::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; background: #a49aff; content: ''; }.activity-tabs button span { padding: .12rem .35rem; border-radius: 999px; background: #ffffff0c; color: #8b8998; font-size: .58rem; }.activity-tabs button.active span { background: #a49aff1a; color: #b6adff; }.activity-table td { height: 3.8rem; }.activity-table .agent-avatar { flex: 0 0 1.8rem; }.log-table td { font-size: .67rem; }.log-time { color: #898797 !important; font-variant-numeric: tabular-nums; }.action-label { display: inline-flex; align-items: center; gap: .4rem; color: #c4c2d0; }.action-label i { width: .42rem; height: .42rem; border-radius: 50%; background: #a49aff; }.action-label .action-tool { background: #79b4ff; }.action-label .action-message { background: #75e0b0; }.action-label .action-reason { background: #c49aff; }
    .service-table-panel { padding: 0; overflow: hidden; }.service-table-scroll { width: 100%; overflow-x: auto; }.service-table { width: 100%; border-collapse: collapse; text-align: left; white-space: nowrap; }.service-table th { height: 2.8rem; padding: 0 1rem; border-bottom: 1px solid #ffffff12; color: #777684; font-size: .62rem; font-weight: 550; }.service-table td { height: 3.65rem; padding: 0 1rem; border-bottom: 1px solid #ffffff0b; color: #c9c8d5; font-size: .72rem; }.service-table tbody tr:last-child td { border-bottom: 0; }.service-table tbody tr:hover { background: #ffffff04; }.service-table th:first-child,.service-table td:first-child { width: 4rem; padding-left: 1.25rem; }.service-number { color: #777684 !important; font-variant-numeric: tabular-nums; }.service-name { display: flex; align-items: center; gap: .65rem; color: #e5e4ef; font-weight: 550; }.service-type-icon { display: grid; width: 1.75rem; height: 1.75rem; place-items: center; border: 1px solid #ffffff12; border-radius: .5rem; background: #ffffff06; color: #aea4ff; font-size: .78rem; }.service-table code { color: #9795a5; font-family: ui-monospace,SFMono-Regular,Consolas,monospace; font-size: .66rem; }.ready-cell { display: flex; align-items: center; gap: .6rem; }.ready-track { width: 4.3rem; height: .32rem; overflow: hidden; border-radius: 999px; background: #ffffff10; }.ready-track i { display: block; height: 100%; border-radius: inherit; background: #75e0b0; }.service-status { display: inline-flex; align-items: center; gap: .4rem; padding: .28rem .5rem; border-radius: 999px; font-size: .62rem; }.service-status i { width: .38rem; height: .38rem; border-radius: 50%; background: currentColor; }.service-status.healthy { background: #75e0b012; color: #75e0b0; }.service-status.degraded { background: #ffc46b12; color: #ffc46b; }.service-status.down { background: #ff788812; color: #ff888f; }.table-footer { display: flex; justify-content: space-between; gap: 1rem; padding: .8rem 1rem; border-top: 1px solid #ffffff0c; color: #777684; font-size: .62rem; }.empty-services { height: 6rem !important; color: #777684 !important; text-align: center; }
    @media (max-width: 850px) {
      .welcome-content { grid-template-columns: 1fr; padding-top: 9rem; }.welcome-art { position: absolute; inset: 12% -10% 10% 35%; min-height: 0; opacity: .48; pointer-events: none; }.welcome-copy { max-width: 34rem; }
      .app-layout { padding-left: 4.5rem; }
      .side-bar { width: 4.5rem; align-items: center; padding: 1rem .45rem; }
      .sidebar-toggle { align-self: center; }.side-heading,.side-link span:last-child,.profile-copy,.profile-more { display: none; }
      .side-menu-group { width: 100%; margin-top: 0; margin-bottom: 1.25rem; }.side-nav { width: 100%; }.side-link { justify-content: center; padding: 0; }.nav-icon { flex-basis: 1.5rem; width: 1.5rem; }
      .side-bottom { justify-content: center; width: 100%; padding-inline: 0; }.top-bar { gap: 1.5rem; padding-inline: 1.5rem; }.brand { min-width: auto; }
      .dashboard { padding-inline: 1rem; }.monitor-grid,.lower-grid { grid-template-columns: minmax(0,1fr); }.metric-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
      .scene-panel, ngt-canvas { min-height: 480px; height: 58vh; }
      .page-footer { position: static; grid-column: 1; margin-top: 1rem; }
    }
    @media (max-width: 520px) {
      .welcome-top { height: 4.25rem; padding-inline: 1.25rem; }.welcome-content { min-height: calc(100vh - 4rem); padding: 7.5rem 1.5rem 5rem; }.welcome-copy h1 { font-size: clamp(2.8rem,12vw,4rem); }.welcome-art { inset: 18% -30% 5% 8%; opacity: .25; }.welcome-footer { inset-inline: 1.25rem; font-size: .48rem; }.welcome-footer span:last-child { display: none; }.login-card { padding: 1.75rem; }
      .app-layout { padding: 3.75rem 0 0; }.top-bar { height: 3.75rem; gap: .8rem; padding-inline: 1rem; }
      .brand { font-size: .7rem; }.brand-mark { width: 1.65rem; height: 1.65rem; }.top-links { gap: .8rem; }.top-link { font-size: .7rem; }
      .top-action { padding: .5rem .6rem; font-size: 0; }.top-action span { font-size: .9rem; }
      .side-bar { inset: auto 0 0; flex-direction: row; width: auto; height: 4rem; padding: .3rem .75rem; border-top: 1px solid #ffffff12; border-right: 0; background: #121319f2; }
      .sidebar-toggle { flex: 0 0 2.6rem; width: 2.6rem; height: 2.6rem; margin: 0 .5rem 0 0; }.side-nav { display: flex; flex: 1; justify-content: space-around; min-width: 0; }.side-link { flex: 0 0 2.65rem; width: 2.65rem; }.side-bottom { display: none; }
      .dashboard { gap: .7rem; padding: 1rem .7rem 5rem; }.dashboard-heading { align-items: flex-start; flex-direction: column; }.dashboard-heading h1 { font-size: 1.4rem; }.live-status { font-size: .6rem; }.metric-grid { gap: .55rem; }.metric-card { padding: .7rem; }.metric-card > strong { font-size: 1.35rem; }.metric-top { font-size: .63rem; }.metric-foot { gap: .3rem; font-size: .53rem; }.monitor-grid,.lower-grid { gap: .65rem; }.panel { padding: .8rem; }.agent-row { grid-template-columns: 1.8rem minmax(0,1fr) auto; gap: .45rem; }.agent-runtime { display: none; }.state-chip { font-size: .5rem; }.activity-chart { height: 9.5rem; }.service-toolbar { flex-wrap: wrap; }.service-search { flex: 1 1 100%; }.filter-control { flex: 0 0 auto; }.table-footer { font-size: .55rem; }.service-table th,.service-table td { padding-inline: .7rem; }
      .scene-panel, ngt-canvas { min-height: 380px; height: 48vh; }
      .page-footer { font-size: 0.5rem; }
    }
  `,
})
export class AppComponent {
  readonly page = signal<'welcome' | 'login' | 'main'>('welcome');
  readonly sidebarCollapsed = signal(false);
  readonly section = signal<'dashboard' | 'activity' | 'service-health'>('dashboard');
  readonly activityTab = signal<'agents' | 'log'>('agents');
  readonly activitySearch = signal('');
  readonly activityFilter = signal('All');
  readonly serviceSearch = signal('');
  readonly serviceStatusFilter = signal('All');
  readonly services = [
    { no: '01', name: 'Orchestrator API', address: '10.0.1.12:8080', ready: 100, status: 'Healthy', icon: '◇' },
    { no: '02', name: 'Agent Runtime', address: '10.0.1.24:9000', ready: 100, status: 'Healthy', icon: '◈' },
    { no: '03', name: 'Task Queue', address: 'redis://queue.internal:6379', ready: 99.8, status: 'Healthy', icon: '≋' },
    { no: '04', name: 'Tool Gateway', address: '10.0.2.18:8081', ready: 96.4, status: 'Degraded', icon: '⌁' },
    { no: '05', name: 'Vector Store', address: '10.0.3.09:6333', ready: 100, status: 'Healthy', icon: '◉' },
    { no: '06', name: 'Model Router', address: '10.0.2.21:8082', ready: 0, status: 'Down', icon: '✳' },
    { no: '07', name: 'Event Collector', address: '10.0.4.16:4317', ready: 99.2, status: 'Healthy', icon: '⌗' },
  ];
  filteredServices() {
    const query = this.serviceSearch().trim().toLowerCase();
    const status = this.serviceStatusFilter();
    return this.services.filter((service) => {
      const matchesQuery = !query || Object.values(service).some((value) => String(value).toLowerCase().includes(query));
      return matchesQuery && (status === 'All' || service.status === status);
    });
  }
  toggleSidebar(): void { this.sidebarCollapsed.update((collapsed) => !collapsed); }
  setSection(section: 'dashboard' | 'activity' | 'service-health'): void { this.section.set(section); }
  setActivityTab(tab: 'agents' | 'log'): void { this.activityTab.set(tab); this.activityFilter.set('All'); }
  setActivitySearch(event: Event): void { this.activitySearch.set((event.target as HTMLInputElement).value); }
  setActivityFilter(event: Event): void { this.activityFilter.set((event.target as HTMLSelectElement).value); }
  activityRowMatches(row: string, category: string): boolean {
    const query = this.activitySearch().trim().toLowerCase();
    const filter = this.activityFilter();
    return (!query || row.toLowerCase().includes(query)) && (filter === 'All' || filter === category);
  }
  activityResultCount(): number {
    const rows = this.activityTab() === 'agents'
      ? [
          ['Research Agent Analyzing market signals 11:02:18 03:42 Running', 'Running'],
          ['Code Assistant Reviewing pull request 284 11:04:42 01:18 Running', 'Running'],
          ['Data Analyst Waiting for user input 10:58:06 Waiting', 'Waiting'],
          ['Writing Agent Generated weekly summary 10:56:32 00:56 Completed', 'Completed'],
        ]
      : [
          ['11:06:42 Research Agent Tool call web_search queried market trends Success', 'Tool call'],
          ['11:05:18 Code Assistant Reasoning Reviewed 8 files in pull request 284 Completed', 'Reasoning'],
          ['11:04:53 Research Agent Message Saved 12 sources to research notes Success', 'Message'],
          ['11:03:10 Data Analyst Tool call sql_query daily active users Retrying', 'Tool call'],
          ['11:02:18 Writing Agent Output Weekly summary draft generated Completed', 'Output'],
          ['11:01:44 Code Assistant Tool call github fetched pull request 284 Success', 'Tool call'],
          ['10:59:31 Research Agent Reasoning Comparing findings across 12 sources Completed', 'Reasoning'],
        ];
    return rows.filter(([row, category]) => this.activityRowMatches(row, category)).length;
  }
  setServiceSearch(event: Event): void { this.serviceSearch.set((event.target as HTMLInputElement).value); }
  setServiceStatusFilter(event: Event): void { this.serviceStatusFilter.set((event.target as HTMLSelectElement).value); }
  goToLogin(): void { this.page.set('login'); }
  goToWelcome(): void { this.page.set('welcome'); }
  signIn(event: Event): void { event.preventDefault(); this.page.set('main'); }
  signOut(): void { this.page.set('welcome'); }
}
