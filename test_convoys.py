import datetime
import matplotlib
import numpy
import pytest
import random
import scipy.special
import scipy.stats
matplotlib.use('Agg')  # Needed for matplotlib to run in Travis
import convoys
import convoys.regression
import convoys.single


def sample_weibull(k, lambd):
    # scipy.stats is garbage for this
    # exp(-(x * lambda)^k) = y
    return (-numpy.log(random.random())) ** (1.0/k) / lambd

def generate_censored_data(N, E, C):
    B = numpy.array([c and e < n for n, e, c in zip(N, E, C)])
    T = numpy.array([e if b else n for e, b, n in zip(E, B, N)])
    return B, T


def test_exponential_regression_model(c=0.3, lambd=0.1, n=100000):
    X = numpy.ones((n, 1))
    C = scipy.stats.bernoulli.rvs(c, size=(n,))  # did it convert
    N = scipy.stats.uniform.rvs(scale=5./lambd, size=(n,))  # time now
    E = scipy.stats.expon.rvs(scale=1./lambd, size=(n,))  # time of event
    B, T = generate_censored_data(N, E, C)
    model = convoys.regression.Exponential()
    model.fit(X, B, T)
    assert 0.95*c < model.predict_final([1]) < 1.05*c
    assert 0.80/lambd < model.predict_time([1]) < 1.20/lambd
    t = 10
    d = 1 - numpy.exp(-lambd*t)
    assert 0.95*c*d < model.predict([1], t) < 1.05*c*d

    # Check the confidence intervals
    y, y_lo, y_hi = model.predict_final([1], ci=0.95)
    c_lo = scipy.stats.beta.ppf(0.025, n*c, n*(1-c))
    c_hi = scipy.stats.beta.ppf(0.975, n*c, n*(1-c))
    assert 0.95*c < y < 1.05*c
    assert 0.70*(c_hi-c_lo) < (y_hi-y_lo) < 1.30*(c_hi-c_lo)


def test_weibull_regression_model(cs=[0.3, 0.5, 0.7], lambd=0.1, k=0.5, n=100000):
    X = numpy.array([[1] + [r % len(cs) == j for j in range(len(cs))] for r in range(n)])
    C = numpy.array([bool(random.random() < cs[r % len(cs)]) for r in range(n)])
    N = scipy.stats.uniform.rvs(scale=5./lambd, size=(n,))
    E = numpy.array([sample_weibull(k, lambd) for r in range(n)])
    B, T = generate_censored_data(N, E, C)

    model = convoys.regression.Weibull()
    model.fit(X, B, T)
    for r, c in enumerate(cs):
        x = [1] + [int(r == j) for j in range(len(cs))]
        assert 0.95 * c < model.predict_final(x) < 1.05 * c
        expected_time = 1./lambd * scipy.special.gamma(1 + 1/k)
        assert 0.80*expected_time < model.predict_time(x) < 1.20*expected_time


def test_weibull_regression_model_ci(c=0.3, lambd=0.1, k=0.5, n=100000):
    X = numpy.ones((n, 1))
    C = scipy.stats.bernoulli.rvs(c, size=(n,))
    N = scipy.stats.uniform.rvs(scale=5./lambd, size=(n,))
    E = numpy.array([sample_weibull(k, lambd) for r in range(n)])
    B, T = generate_censored_data(N, E, C)

    model = convoys.regression.Weibull()
    model.fit(X, B, T)
    y, y_lo, y_hi = model.predict_final([1], ci=0.95)
    c_lo = scipy.stats.beta.ppf(0.025, n*c, n*(1-c))
    c_hi = scipy.stats.beta.ppf(0.975, n*c, n*(1-c))
    assert 0.95*c < y < 1.05 * c
    assert 0.70*(c_hi-c_lo) < (y_hi-y_lo) < 1.30*(c_hi-c_lo)


def test_gamma_regression_model(c=0.3, lambd=0.1, k=3.0, n=100000):
    # TODO: this one seems very sensitive to large values for N (i.e. less censoring)
    X = numpy.ones((n, 1))
    C = scipy.stats.bernoulli.rvs(c, size=(n,))
    N = scipy.stats.uniform.rvs(scale=20./lambd, size=(n,))
    E = scipy.stats.gamma.rvs(a=k, scale=1.0/lambd, size=(n,))
    B, T = generate_censored_data(N, E, C)

    model = convoys.regression.Gamma()
    model.fit(X, B, T)
    assert 0.95*c < model.predict_final([1]) < 1.05*c
    assert 0.90*k < model.params['k'] < 1.10*k
    assert 0.90*lambd < numpy.exp(model.params['alpha']) < 1.10*lambd
    assert 0.80*k/lambd < model.predict_time([1]) < 1.20*k/lambd


def test_plot_cohorts(cs=[0.3, 0.5, 0.7], k=0.5, lambd=0.1, n=10000):
    C = numpy.array([bool(random.random() < cs[r % len(cs)]) for r in range(n)])
    N = scipy.stats.uniform.rvs(scale=5./lambd, size=(n,))
    E = numpy.array([sample_weibull(k, lambd) for r in range(n)])
    B, T = generate_censored_data(N, E, C)
    data = []
    x2t = lambda x: datetime.datetime(2000, 1, 1) + datetime.timedelta(days=x)
    for i, (b, t, n) in enumerate(zip(B, T, N)):
        data.append(('Group %d' % (i % len(cs)),  # group name
                     x2t(0),  # created at
                     x2t(t) if b else None,  # converted at
                     x2t(n)))  # now

    matplotlib.pyplot.clf()
    result = convoys.plot_cohorts(data, model='weibull')
    matplotlib.pyplot.savefig('weibull.png')
    group, y, y_lo, y_hi = result[0]
    c = cs[0]
    assert group == 'Group 0'
    assert 0.95*c < y < 1.05 * c

    # Also plot with default arguments
    matplotlib.pyplot.clf()
    convoys.plot_cohorts(data)
    matplotlib.pyplot.savefig('kaplan-meier.png')
    group, y, y_lo, y_hi = result[0]
    c = cs[0]
    assert group == 'Group 0'
    assert 0.95*c < y < 1.05 * c


def test_nonparametric_model(c=0.3, lambd=0.1, k=0.5, n=10000):
    C = scipy.stats.bernoulli.rvs(c, size=(n,))
    N = scipy.stats.uniform.rvs(scale=30./lambd, size=(n,))
    E = numpy.array([sample_weibull(k, lambd) for r in range(n)])
    B, T = generate_censored_data(N, E, C)

    m = convoys.single.Nonparametric()
    m.fit(B, T)

    assert 0.95*c < m.predict_final() < 1.05*c

    print(m.predict(1, ci=0.95))
    print(m.predict([1, 2], ci=0.95))
