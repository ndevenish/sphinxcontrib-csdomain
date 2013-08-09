.. Sphinx CS Domain documentation master file, created by
   sphinx-quickstart on Sat Aug  3 23:10:46 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Sphinx CS Domain's documentation!
============================================

Contents:

.. toctree::
   :maxdepth: 2



..  cs:method:: public void SetError(bool hasError, string description = null, [CallerMemberName] string property = null)
    :namespace: StylePack.Foo

    A member method on the class

  
.. cs:visibility:: public

.. cs:namespace:: StylePack.Utils

..  cs:class:: protected class ViewModel<T, Q> : IViewModel, IEditableObject, INotifyDataErrorInfo where T : class, IModelClass, new()
    :namespace: StylePack.Another
    
    The parent ViewModel.
    
    ..  cs:method:: public void SetError(bool hasError, string description = null, [CallerMemberName] string property = null)

      A member method on the class

    .. cs:property:: public bool HasErrors { get; private set; }

      A property on the class

.. cs:member:: public SetErrorConstructor(bool hasError, string description = null, [CallerMemberName] string property = null)

.. cs:interface:: public interface IVisibleModelClass : IModelClass

  inside the interface, is:

  .. cs:member:: public bool SomeProp { get; }
    
    Some member property

.. cs:member:: public bool SomeProp { get; }
  :namespace: another.namespace
  
  Some member property

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

