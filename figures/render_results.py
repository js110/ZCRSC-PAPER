#!/usr/bin/env python3
"""Restyle measured results without rerunning experiments or changing raw data."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXP = ROOT/'experiments'
BLUE, ORANGE, GREY = '#0072B2', '#D55E00', '#555555'
SOURCES = {}
FIGURES = []
WIDTH = 6.1  # 154.94 mm; provisional review size, not a journal mandate.


def read(name):
    path = EXP/name
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


def axis(ax):
    ax.grid(axis='y', color='#E4E7EB', linewidth=.55)
    ax.tick_params(length=3)


def export(fig, name, description, transformation, rows):
    fig.canvas.draw()
    # All outputs are new presentation artifacts, never raw experiment files.
    for suffix in ('pdf', 'svg', 'png'):
        fig.savefig(HERE/f'{name}.{suffix}', dpi=600, facecolor='white',
                    transparent=False, bbox_inches=None)
    with (HERE/f'{name}_data.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    FIGURES.append(dict(name=name, description=description,
                        transformations=transformation,
                        width_inches=float(fig.get_figwidth()),
                        height_inches=float(fig.get_figheight()),
                        source_data_table=f'{name}_data.csv'))
    plt.close(fig)


def interval(stat):
    return 100*np.array([stat['mean'], stat['ci95_low'], stat['ci95_high']])


def availability():
    results = read('semantic_results.json')
    fig, ax = plt.subplots(figsize=(WIDTH, 2.05), layout='constrained')
    rows = []
    for method, label, color, marker, ls in (
        ('robust_depth', 'Robust set', BLUE, 'o', '-'),
        ('fixed_margin', 'Fixed margin', ORANGE, 's', '--')):
        stats = []
        for radius in (2,4,6):
            key = f'calibrated_correlated__radius_{radius}__byz_1'
            stat = results['aggregate'][key][method]['decisive_coverage']
            mean, low, high = interval(stat)
            stats.append((mean,low,high))
            rows.append(dict(method=label, radius_quantized=radius, mean_percent=mean,
                             ci95_low_percent=low, ci95_high_percent=high, seeds=30))
        y, low, high = np.array(stats).T
        ax.errorbar([2,4,6], y, yerr=[y-low,high-y], color=color, marker=marker,
                    ls=ls, capsize=3, elinewidth=.9, label=label, markersize=5)
    ax.set(xlabel='Maximum box radius (quantized units)', ylabel='Decisive coverage (%)',
           xticks=[2,4,6], ylim=(0,100), xlim=(1.6,6.4))
    ax.legend(loc='lower left', ncol=2)
    axis(ax)
    export(fig, 'availability',
           'Robust-set and fixed-margin decisive coverage versus radius, with seed-level uncertainty.',
           'Same calibrated correlated, one-Byzantine conditions as the previous figure. '
           'Mean and stored normal 95% CI over 30 seeds; percentage conversion only. '
           'Straight segments guide the eye, with no smoothing or interpolation estimates.', rows)


def backend_costs():
    shapes = [(3,2),(4,2),(5,2),(3,3),(4,3)]
    fig, axes = plt.subplots(1,2,figsize=(WIDTH,3.15),layout='constrained')
    rows=[]
    for backend, prefix, color, marker, offset in (
        ('Lower-corner','zkdepth',ORANGE,'s',-.13),
        ('Subset','subset',BLUE,'o',.13)):
        constraints=[]
        for j,(n,d) in enumerate(shapes):
            result=read(f'{prefix}_n{n}_d{d}_formal.json')
            values=np.asarray(result['prove_ms'])
            assert len(values)==30
            constraints.append(result['constraints']/1000)
            x=j+offset
            # Wider deterministic strip: keep every measured y-value but avoid
            # translucent hollow-marker overlap that appears blurred in PDF viewers.
            jitter=np.linspace(-.075,.075,len(values))
            axes[1].scatter(x+jitter,values,s=6,c=color,marker=marker,
                            linewidths=0,alpha=.42,zorder=2)
            p05,p50,p95=np.quantile(values,[.05,.5,.95])
            axes[1].errorbar(x,p50,yerr=[[p50-p05],[p95-p50]],fmt=marker,
                             color=color,capsize=3.5,markersize=5.2,
                             markeredgecolor='white',markeredgewidth=.55,
                             elinewidth=1.2,zorder=3)
            for i,v in enumerate(values):
                rows.append(dict(backend=backend,n=n,d=d,repetition=i+1,
                                 constraints=result['constraints'],prove_ms=v,
                                 p05_ms=p05,p50_ms=p50,p95_ms=p95))
        axes[0].plot(np.arange(5)+offset,constraints,ls='none',marker=marker,
                     markersize=5,color=color,label=backend)
    for ax,title in zip(axes,('(a) Circuit size','(b) Proving time')):
        axis(ax)
        ax.set_title(title,loc='left',fontweight='bold',pad=9)
        ax.set(xticks=range(5),xticklabels=[f'({n},{d})' for n,d in shapes],
               xlabel='Circuit shape (n, d)',xlim=(-.5,4.5),ylim=(0,None))
        ax.axvline(2.5,color='#999999',ls=':',lw=.7)
        ax.text(.32,.97,'2D',transform=ax.transAxes,ha='center',va='top',fontsize=7,color=GREY)
        ax.text(.79,.97,'3D',transform=ax.transAxes,ha='center',va='top',fontsize=7,color=GREY)
    axes[0].set_ylabel('Constraints (thousands)')
    axes[1].set_ylabel('Proving time (ms)')
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,.89),fontsize=7)
    export(fig,'backend_costs',
           'Five matched circuit shapes. Subset uses fewer constraints and lower proving times in the measured small-fault regime. All 300 timing observations are shown.',
           'Constraints divided by 1000. Raw 30 proof times per shape/backend are shown as small filled markers; '
           'larger markers show medians and whiskers are 5th–95th sample percentiles, NOT confidence intervals. '
           'Deterministic horizontal displacement separates repeated timings; no y-value jitter or smoothing. '
           'Backend batches were separate, not randomized interleaved comparisons.',rows)


def budget_tradeoff():
    fig,axes=plt.subplots(1,3,figsize=(WIDTH,2.65),layout='constrained')
    rows=[]
    results=[read('semantic_results.json'),read('semantic_results_r1.json'),read('semantic_results_r2.json')]
    for model,label,color,marker,ls in (
        ('calibrated_correlated','Calibrated',BLUE,'o','-'),
        ('undercovered_correlated','Undercovered',ORANGE,'s','--')):
        values=[]
        for r,result in enumerate(results):
            stats=result['aggregate'][model+'__radius_4__byz_1']['robust_depth']
            for metric in ('decisive_coverage','false_accept_rate','false_reject_rate'):
                mean,low,high=interval(stats[metric])
                rows.append(dict(model=label,r=r,metric=metric,mean_percent=mean,
                                 ci95_low_percent=low,ci95_high_percent=high,seeds=30))
            values.append(interval(stats['decisive_coverage']))
        y,low,high=np.array(values).T
        # Tiny x offset separates nearly equal means; nominal r values unchanged.
        xs=np.arange(3)+(-.035 if model.startswith('calibrated') else .035)
        axes[0].errorbar(xs,y,yerr=[y-low,high-y],color=color,marker=marker,
                         ls=ls,capsize=3,label=label)
    for idx,(metric,label,color,marker,ls) in enumerate((
        ('false_accept_rate','False accept',BLUE,'o','-'),
        ('false_reject_rate','False reject',ORANGE,'s','--')),start=1):
        vals=[interval(r['aggregate']['undercovered_correlated__radius_4__byz_1']['robust_depth'][metric]) for r in results]
        y,low,high=np.array(vals).T
        axes[idx].errorbar(range(3),y,yerr=[y-low,high-y],color=color,marker=marker,
                         ls=ls,capsize=3,label=label,clip_on=False)
    for ax,title in zip(axes,('(a) Availability','(b) False accept','(c) False reject')):
        axis(ax)
        ax.set_title(title,loc='left',fontweight='bold',pad=9)
        ax.set(xlabel='Budget r',xticks=[0,1,2],xlim=(-.2,2.2))
    axes[0].legend(loc='lower left',fontsize=6.5)
    axes[0].set(ylabel='Coverage (%)',ylim=(0,100))
    for ax in axes[1:]:
        ax.set(ylabel='Conditional rate (%)',ylim=(0,None))
        ax.text(.97,.96,'Undercovered',transform=ax.transAxes,ha='right',va='top',fontsize=6.5)
    # Stored normal intervals can cross zero; preserve their full extent.
    axes[2].set_ylim(bottom=-.6)
    axes[2].axhline(0,color=GREY,lw=.7)
    export(fig,'budget_tradeoff',
           'Increasing r reduces decisive coverage. Under misspecified uncertainty, false rejection falls but remains nonzero; false acceptance also appears at r=0.',
           'Stored means and normal 95% seed intervals. Same 30 seeds reused across budgets. '
           'n=5, f=1, radius=4, one Byzantine source. Calibrated error means are zero for all budgets '
           'and remain in the source table; panels b and c show the undercovered condition with separate y scales. '
           'No budget re-tuning or independent-sample inflation.',rows)


def receiver():
    summary=read('receiver_calibration.json')
    path=EXP/'receiver_residuals.csv'
    SOURCES[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open() as stream:
        rows=list(csv.DictReader(stream))
    start=float(rows[0]['gps_second'])
    fig,ax=plt.subplots(figsize=(WIDTH,2.85),layout='constrained')
    radius=summary['radius_m']
    for split,label,color,marker in (
        ('calibration','Calibration (78)',BLUE,'o'),
        ('gap','Gap (10)',GREY,'x'),
        ('evaluation','Evaluation (69)',ORANGE,'s')):
        subset=[r for r in rows if r['split']==split]
        ax.plot([float(r['gps_second'])-start for r in subset],
                [float(r['score_m']) for r in subset],ls='none',color=color,
                marker=marker,markersize=2.7,label=label)
    ax.axvspan(77.5,87.5,color='#F1F2F4',zorder=0)
    ax.axhline(radius,color='#222222',ls='--',lw=1)
    ax.set(xlabel='Elapsed time (s)',
           ylabel=r'$\max(|e_E|, |e_N|)$ (m)',xlim=(-2,158),ylim=(0,1.65))
    for split,x,label,color in (('calibration',35,'Calibration',BLUE),('evaluation',123,'Evaluation',ORANGE)):
        scores=[float(r['score_m']) for r in rows if r['split']==split]
        count=sum(v<=radius for v in scores)
        ax.text(x,1.47,f'{label}\nCovered: {count}/{len(scores)}',ha='center',va='top',color=color,fontsize=8)
    ax.text(82.5,1.50,'Gap\n10',ha='center',va='top',color=GREY,fontsize=7)
    ax.text(155,radius-.04,'Fixed threshold: 0.864 m',ha='right',va='top',fontsize=7)
    axis(ax)
    export(fig,'receiver_diagnostic',
           'All 157 static-receiver residual scores, including the ten-epoch gap, and the fixed calibration threshold. Only 2 of 69 evaluation scores lie at or below the threshold.',
           'Plot max(abs(east),abs(north)), not Euclidean horizontal distance. '
           'Elapsed time subtraction only. No smoothing or lines across gaps. '
           'All rows preserved. Retrospective combined solution, not online independent trials.',rows)


def main():
    with plt.style.context(HERE/'publication.mplstyle'), plt.rc_context({
        'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,
        'axes.titlesize':9,'xtick.labelsize':8,'ytick.labelsize':8,
        'legend.fontsize':8,'lines.linewidth':1.2,'svg.fonttype':'none'}):
        availability()
        backend_costs()
        budget_tradeoff()
        receiver()
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
               for path,digest in SOURCES.items()), 'Source changed while plotting'
    manifest=dict(date='2026-09-29',journal='Journal of Information Security and Applications',phase='pre-submission revision',
                  journal_specific_figure_rules='tracked in venue_template_jisa/COMPLIANCE.md; final portal checks remain author-side',
                  sources=SOURCES,figures=FIGURES,matplotlib=matplotlib.__version__,numpy=np.__version__,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  raster_dpi=600,vector_formats=['pdf','svg'],grayscale_support='redundant markers and line styles; manual review required')
    (HERE/'figure_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Created four evidence-bound figures; raw inputs unchanged.')


if __name__=='__main__':
    main()
