from django.conf.urls import url
from primsa import views


#uses regular expression to point URL requests to functional Views in views.py
urlpatterns=[
    url(r'^$',views.index, name='index'),
    url(r'^ncbi/$',views.ncbi, name='ncbi'),
    url(r'^ncbi/download/$',views.download, name='download'),
    url(r'^ncbi/download/clustal/$',views.clustal, name='clustal'),
    url(r'^msa/$',views.msa, name='msa'),
]
