"""
Run multiple hypothesis tests
"""

import pandas as pd
import numpy as np
from statsmodels.sandbox.stats.multicomp import multipletests
import logging


def compute_all_stats(investigations, exact=True, level=0.95):
    """
    Compute all statistics for all investigations and protected features

    Parameters
    ----------
    investigations :
        list of investigations

    exact :
        whether exact tests should be used

    level :
        overall confidence level (1- familywise error rate)

    Returns
    -------
    all_stats:
        list of all statistics for all investigations
    """

    # count the number of hypotheses to test
    total_hypotheses = sum([num_hypotheses(inv) for inv in investigations])
    logging.info('Testing %d hypotheses', total_hypotheses)

    #
    # Adjusted Confidence Level (Bonferroni)
    #
    adj_level = 1-(1-level)/total_hypotheses

    # statistics for all investigations
    all_stats = [{sens: compute_stats(ctxts, exact, adj_level)
                  for (sens, ctxts) in sorted(inv.contexts.iteritems())}
                 for inv in investigations]

    # flattened array of all p-values
    all_pvals = [max(stat[-1], 1e-180)
                 for inv_stats in all_stats
                 for sens_stats in inv_stats.values()
                 for stat in sens_stats['stats']]

    # correct p-values
    _, pvals_corr, _, _ = multipletests(all_pvals,
                                        alpha=1-level,
                                        method='holm')

    # replace p-values by their corrected value
    idx = 0
    # iterate over all investigations
    for inv_idx, inv in enumerate(investigations):
        # iterate over all protected features for an investigation
        for (sens, sens_contexts) in inv.contexts.iteritems():
            sens_stats = all_stats[inv_idx][sens]['stats']
            # iterate over all contexts for a protected feature
            for i in range(len(sens_stats)):
                old_stats = sens_stats[i]
                all_stats[inv_idx][sens]['stats'][i] = \
                    np.append(old_stats[0:-1], pvals_corr[idx])
                idx += 1

    for inv_idx, inv in enumerate(investigations):
        for (sens, sens_contexts) in inv.contexts.iteritems():
            metric = sens_contexts[0].metric
            # For regression, re-form the dataframes for each context
            if isinstance(metric.stats, pd.DataFrame):
                res = all_stats[inv_idx][sens]
                res = pd.DataFrame(res['stats'], index=res['index'],
                                   columns=res['cols'])
                all_stats[inv_idx][sens] = \
                    {'stats':
                         np.array_split(res, len(res)/len(metric.stats))}

    all_stats = [{sens: sens_stats['stats']
                  for (sens, sens_stats) in inv_stats.iteritems()}
                 for inv_stats in all_stats]

    return all_stats


def num_hypotheses(inv):
    """
    Counts the number of hypotheses to be tested in a single investigation

    Parameters
    ----------
    inv :
        an investigation

    Returns
    -------
    tot :
        the total number of hypotheses to test
    """
    tot = 0
    for contexts in inv.contexts.values():
        metric = contexts[0].metric
        if isinstance(metric.stats, pd.DataFrame):
            tot += len(contexts)*len(metric.stats)
        else:
            tot += len(contexts)

    return tot


def compute_stats(contexts, exact, level):
    """
    Compute statistics for a list of contexts

    Parameters
    ----------
    contexts :
        a list of contexts

    exact :
        whether exact statistics should be computed

    level :
        confidence level

    Returns
    -------
    dict :
        a dictionary containing the computed statistics as well as index
        information if more than one hypothesis was tested in a context
    """
    metric = contexts[0].metric
    stats = [c.metric.compute(c.data, level, exact=exact).stats
             for c in contexts]

    # For regression, we have multiple p-values per context
    # (one per topK coefficient)
    if isinstance(metric.stats, pd.DataFrame):
        stats = pd.concat(stats)
        index = stats.index
        cols = stats.columns
        stats = stats.values
        return {'stats': stats, 'index': index, 'cols': cols}

    return {'stats': stats}