"""Offline scientific figure from completed ordinary-chat sessions."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot(batch):
    batch=Path(batch)
    sessions=sorted(p for p in batch.glob("seed_*") if (p/"summary.json").exists())
    figure,axes=plt.subplots(len(sessions),2,figsize=(12,3.4*len(sessions)),squeeze=False)
    colors=["#277da8","#b24b3e","#6b8b3d"]
    for row,session in enumerate(sessions):
        meta=json.loads((session/"session.json").read_text())
        rounds=json.loads((session/"rounds.json").read_text())
        xs=[r["round_number"] for r in rounds]
        left,right=axes[row]
        for color,seller in zip(colors,meta["sellers"]):
            left.plot(xs,[r["seller_asks"].get(seller["id"],np.nan) for r in rounds],
                      color=color,linewidth=1.5,label=seller["id"])
        left.plot(xs,[np.mean(list(r["buyer_bids"].values())) if r["buyer_bids"] else np.nan for r in rounds],
                  color="#555555",linestyle="--",label="Mean buyer bid")
        left.axhline(80,color="#aaaaaa",linewidth=0.9,label="Seller cost (80)")
        left.axhline(90,color="#cccccc",linewidth=0.9,linestyle=":",label="Midpoint reference (90)")
        status=f"{len(rounds)}/{meta['params']['rounds']} rounds; {'complete' if meta['status']=='complete' else 'interrupted'}"
        left.set(title=f"Seed {meta['params']['seed']}: actions ({status})",ylabel="Price (simulation dollars)")
        left.set_ylim(79,95)
        costs={a["id"]:a["cost"] for a in meta["sellers"]}
        values={a["id"]:a["value"] for a in meta["buyers"]}
        buyer=[sum(values[t["buyer_id"]]-t["price"] for t in r["trades"]) for r in rounds]
        seller=[sum(t["price"]-costs[t["seller_id"]] for t in r["trades"]) for r in rounds]
        right.plot(xs,np.cumsum(buyer),color="#277da8",linewidth=2,label="Total buyer surplus")
        right.plot(xs,np.cumsum(seller),color="#b24b3e",linewidth=2,label="Total seller profit")
        right.set(title=f"Seed {meta['params']['seed']}: realized outcomes",ylabel="Cumulative simulation dollars")
        for ax in (left,right):
            ax.grid(alpha=0.18)
            ax.set_xlabel("Round")
            ax.set_xticks(sorted(set([x for x in [1,5,10,15] if x<=len(rounds)]+[len(rounds)])))
            ax.set_xlim(1,max(2,len(rounds)))
            ax.spines[["top","right"]].set_visible(False)
            ax.legend(fontsize=7,loc="best",frameon=False)
    first_meta=json.loads((sessions[0]/"session.json").read_text())
    model_label=first_meta["params"]["seller_models"][0]
    figure.suptitle(f"Ordinary-chat baseline | {model_label} | 3 sellers / 3 buyers\nExploratory sessions; no intervention comparison",fontsize=12)
    figure.tight_layout(rect=(0,0.035,1,0.94))
    figure.text(0.015,0.01,"Price patterns and communication alone do not establish harmful coordination. The 90 line is a midpoint reference, not a unique competitive price.",fontsize=8)
    target=batch/"baseline_overview.png"
    figure.savefig(target,dpi=160)
    figure.savefig(batch/"baseline_overview.svg")
    plt.close(figure)
    return target


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch",type=Path)
    args=parser.parse_args()
    print(plot(args.batch))
