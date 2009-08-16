# -*- python -*-
#
#       OpenAlea.mtg
#
#       Copyright 2008-2009 INRIA - CIRAD - INRA  
#
#       File author(s): Christophe Pradal <christophe.pradal.at.cirad.fr>
#
#       Distributed under the Cecill-C License.
#       See accompanying file LICENSE.txt or copy at
#           http://www.cecill.info/licences/Licence_CeCILL-C_V1-en.html
# 
#       OpenAlea WebSite : http://openalea.gforge.inria.fr
#
################################################################################
''' This module implement a solver to build 3D representation of a plant mockup 
based on various infomation.

:Principles:
    Use topologic information and associated properties to reconstruct a 3D representation 
    of a plant. The 3D representation must satisfy all the intra and inter topological constraints
    and the properties defined by the user.

:Algorithm:


:Examples:

.. todo::
    - define a set of algorithms that can be used independently (as plug'in).
    - for each algo:
        * Decompose the problem into subproblems by computing the frontere.
          =>define a color based on the properties and the semantic.
          => define a partial order for solving each problems 
        * Solve each subproblems and assemble the solutions
        * Return the solution as properties
    - define a generic method (or methods) to build a geometric object for computed values and properties.

    - diameter
    - length vs points
    - angles

    - remove noise from points
    - translate the branch at the extremities of the cylinder.
'''
import sys
import traversal
from dresser import DressingData
import algo
from mtg import colored_tree, PropertyTree
from math import sqrt

from vplants.plantgl.all import * 

error = False
epsilon = 1e-5

class PlantFrame(object):
    ''' Engine to compute the geometry of a plant based on 
    its topological description and parameters.
    '''

    def __init__(self, g, *args, **kwds):
        ''' Compute a geometric representation of a plant.

        Compute the skeleton of the MTG with a Frame linked to each elements.
        
        :Parameters:
            - g: MTG representing the plant architecture at different scales.
        '''

        # Express everything in degrees or radians. 
        # Do not mix both.

        # Define the inference algorithms to compute missing parameters.
        # Add new algorithms as:
        #   - Visitors 
        #   - plug'in.
        #   - derivation

        # 1. Get the different parameters
        # 2. Build for each element at a given scale the frames.
        # 3 Solve the different constraints by using a plug'in mechanism
        # 4. Design new algo and define new parameters.
        # 5. Use WeberPenn with MTG



        self.g = g
        self.max_scale = g.max_scale()

        # Global parameters
        self.origin = kwds.get('origin', (0,0,0))
        self.dresser = kwds.get('DressingData', DressingData())

        # properties defined for each vertex.
        # length define the length of a vertex
        self.length = self._extract_properties('Length', kwds)
        self.top_diameter = self._extract_properties('TopDiameter', kwds)
        self.bottom_diameter = self._extract_properties('BottomDiameter', kwds)

        # Absolute coordinate of the components
        self.xx= self._extract_properties('XX', kwds)
        self.yy = self._extract_properties('YY', kwds)
        self.zz = self._extract_properties('ZZ', kwds)

        # Absolute euler angles in degree
        self.aa= self._extract_properties('AA', kwds)
        self.bb = self._extract_properties('BB', kwds)
        self.cc = self._extract_properties('CC', kwds)

        self.alpha = self._extract_properties('Alpha', kwds)

        # Relative angles: TO BE DEFINED: alpha, beta, rolll
        # Curves associated to an element
        # Geometry associated to an element with mtg parameters

        # User define axes: Return True or False
        self.new_axe = self._extract_properties('Axe', kwds)
        self.axes = {}

        
 
        self._compute_global_data()
        self.propagate_constraints()


    def _extract_properties(self, name, kwds):
        ''' Extract the property from properties of the mtg 
        or from a user given function.
        '''
        d = {}

        func = kwds.get(name)
        if func:
            # Compute the value for all vertices
            all_values = ((vid,func(vid)) for vid in self.g.vertices())
            # Select only those which are defined
            values = ( (vid, fvid) for vid, fvid in all_values if fvid is not None)

            d = dict(values)
            
        name_property = self.g.property(name).copy()
        name_property.update(d)

        if name in ['XX', 'YY', 'ZZ', 'Length']:
            factor = 1./self.dresser.length_unit
        elif name in ['TopDiameter', 'BottomDiameter']:
            factor = 1./self.dresser.diameter_unit
        elif name in ['Alpha', 'AA', 'BB', 'CC']:
            factor = 1./self.dresser.alpha_unit
        else:
            return name_property
            
        for k, v in name_property.iteritems():
            name_property[k] = factor * v

        return name_property
        
        

    def _compute_global_data(self):
        """
        Scale the values according to units.
        """
        g = self.g
        self.points = {}
        points = self.points
        for vid in self.xx:
            try:
                points[vid] = self.xx[vid], self.yy[vid], self.zz[vid]
            except:
                continue

        self.euler_angles = {}
        angles = self.euler_angles
        for vid in self.aa:
            try:
                angles[vid] = self.aa[vid], self.bb[vid], self.cc[vid]
            except:
                continue
        
        if not self.new_axe:
            self.new_axe = [v for v in g.vertices(scale = self.max_scale) if g.edge_type(v) == '+']

        # Method to compute the axes and their order.
        self._compute_axes()


    def _compute_axes(self):
        """
        Compute the axes with their order.
        """
        if self.axes:
            return

        g = self.g
        max_scale = self.max_scale
        marked = {}
        axes = self.axes
        new_axe = self.new_axe

        self.max_order_axes = 0

        def ancestors(v):
            while v is not None:
                yield v
                marked[v] = True
                if g.parent(v) is None or v in new_axe:
                    break
                v = g.parent(v)
                
        def order(v):
            _order = 0
            while v is not None:
                if v in new_axe:
                    _order += 1
                v = g.parent(v)
            return _order

        for root in g.roots(scale=max_scale):
            for vid in traversal.post_order(g, root):
                if vid in marked:
                    continue
                _axe = list(reversed(list(ancestors(vid))))
                _order = order(_axe[0])
                axes.setdefault(_order, []).append(_axe)


        
    def _get_origin(self, vid):
        ''' Compute the origin for the vertex `vid`.
        '''
        # 1. compute the origin of the tree
        # Check if a complex has origin
        origin = self.origin
        vid = self.g.complex(vid)
        while vid:
            if vid in self.points:
                origin = self.points[vid]
                break
            else:
                vid = self.g.complex(vid)
        self.origin = origin
        return self.origin

    def run(self, scale= -1):
        '''Compute the geometry of the plant.
        '''
        
        if scale == -1:
            scale = self.g.max_scale()

        # TODO: Compute the plantframe for several plants.
        root = list(self.g.roots(scale=scale))[0]

        # 1. compute the origin of the tree
        # Check if a complex has origin
        self.origin = self._get_origin(root)

        axes = compute_axes(self.g, root, self.points, self.origin)
        
        # Compute the points
        # 1. compute fixed points
        # 
        

    def propagate_constraints(self):
        """ Propagate the properties into the whole MTG.
        """
        g = self.g
        # diameter
        max_scale = g.max_scale()
        # Between scale constraints
        # Copy of the keys because we modify the
        for vid in self.bottom_diameter.keys():
            scale = g.scale(vid)
            if scale == max_scale:
                continue
            for s in range(scale+1, max_scale+1):
                roots = g.component_roots_at_scale(vid, s)
                try:
                    component_id = roots.next()
                    self.bottom_diameter[component_id] = self.bottom_diameter[vid] 
                except StopIteration:
                    pass

        # Within scale constraint
        # BottomDiameter(x) = TopDiameter(Parent(x))
        # WARNING : This is NOT TRUE:
        #  - You may have several bot_dia values for the same parent.
        edge_type  = g.property('edge_type')
        for vid in self.bottom_diameter:
            pid = g.parent(vid)
            if pid is not None :
                if pid not in self.top_diameter \
                and (g.nb_children(pid) == 1 or edge_type.get(vid) == '<'):
                    self.top_diameter[pid] = self.bottom_diameter[vid]


        # WARNING: We may have several extremities for the components.
        for vid in self.top_diameter.keys():
            scale = g.scale(vid)
            if scale == max_scale:
                continue
            last = None
            if self.is_linear(g, vid):
                last = self._last_component(g, vid)
                if last not in self.top_diameter:
                    self.top_diameter[last] = self.top_diameter[vid]
            for s in range(scale+2, max_scale):
                if self.is_linear(g, last):
                    last = self._last_component(g, last)
                    if last not in self.top_diameter:
                        self.top_diameter[last] = self.top_diameter[vid]



    ################################################################
    # Methods that extend MTG
    @staticmethod
    def _first_component(g, vid):
        return self.g.component_roots(vid).next()
    @staticmethod
    def _last_component(g, vid):
        leaves = algo.extremities(g, vid, scale=g.scale(vid)+1, ContainedIn=vid)
        return leaves.next()

    @staticmethod
    def _first_component_at_scale(g, vid, scale):
        return g.component_roots_at_scale(vid, scale).next()
    @staticmethod
    def _last_component_at_scale(g, vid, scale):
        leaves = algo.extremities(g, vid, scale=scale, ContainedIn=vid)
        return leaves.next()
        
    @staticmethod
    def is_linear(g, cid):
        """ 
        A complex is linear iff there is only there is only one extremity in it.
        """
        leaves = algo.extremities(g, cid, scale=g.scale(cid)+1, ContainedIn=cid)
        return len(list(leaves)) == 1
        
    @staticmethod
    def strahler_order(g, vid):
        strahler = {}
        for v in traversal.post_order(g, vid):
            children_order = [strahler[c] for c in g.children(v)]
            if children_strahler:
                m, M = min(children_strahler), max(children_strahler)
                strahler[v] = M if m != M else M+1
            else: 
                strahler[v] = 1
        return strahler

    ###########################################################################################
    # Algorithms for the different versions
    ###########################################################################################

    ################################################################
    # Write the different plugins

    ################################################################
    # Diameter algorithms

    def algo_diameter(self, mode=1, power = 2):
        """
        Compute the radius for each vertices.
        Cases:
            1. No radius values at all : pipe model
            2. Linear interpolation of radius on axes.
            3. Pipe model
        """
        if not self.top_diameter and not self.bottom_diameter:
            mode = 0
        
        if mode == 0:
            diameter = self.default_algo_diameter(power)
        else:
            #diameter = self.advanced_algo_diameter(power)
            diameter = self.advanced_algo_diameter2(power)

        return diameter

    def default_algo_diameter(self, power):
        """ 
        Compute the paipe model on the entire mtg.
        When a node has no values, take the deafult value.
        """
        g = self.g
        max_scale = g.max_scale()
        v = g.roots(scale=max_scale).next()

        # Compute default diameter
        dresser = self.dresser
        default_diameter = 1 if not dresser.min_topdia else min(dresser.min_topdia.values())
        default_diameter *= 1./self.dresser.diameter_unit

        strands = {}
        for vid in traversal.post_order(g, v):
            strands[vid] = max(sum([strands[c] for c in g.children(vid)]), 1)

        diameters = {}
        for vid, s in strands.iteritems():
            diameters[vid] = default_diameter * pow(s, 1./power)

        return diameters

    def advanced_algo_diameter(self, power, default_diameter=None):
        """ 
        Compute the pipe model on the entire mtg.

        There are 4 cases:
            for each component:
                - traverse in a post_order way all the vertices
                    -  compute strands and diameter
                    - compute the difference at the root
                    - compute a diameter value for the strands

                - fix problem with wrong power value:
                    The diameter has to be decreasing.
                - if no value for the root, compute the total strands for the tree.
                - Then  divide by the defined radius values obtain from step 1.

        May be improved by a filtering pass.
        Select all the segment without ramification (linear) and interpolate the radius.
        """
        g, new_map = self.build_mtg_from_radius()
        max_scale = g.max_scale()
        dresser = self.dresser
        if default_diameter is None:
            default_diameter = 1 if not dresser.min_topdia else min(dresser.min_topdia.values())
            default_diameter *= 1./self.dresser.diameter_unit

        default_diameter = default_diameter**power


        strands = {}
        diameters = {}

        # update the defined properties with the new indices
        top_diameter = {}
        bottom_diameter = {}
        for v in g.vertices(scale=2):
            old_v = new_map[v]
            if old_v in self.top_diameter:
                top_diameter[v] = self.top_diameter[old_v]
            if old_v in self.bottom_diameter:
                bottom_diameter[v] = self.bottom_diameter[old_v]

        for k,td in top_diameter.iteritems():
            diameters[k] = td**power
        ###
        error_vertex = []
        # For each independant sub_systems
        
        for cid in g.vertices(scale=1):
            # traverse the tree in a post_order way only for all vid in cid
            root = g.component_roots(cid).next()
            has_root_diameter = root in diameters or root in bottom_diameter or g.parent(root) in diameters
            if has_root_diameter:
                pid = g.parent(root)
                if pid in diameters:
                    root_diameter = diameters[g.parent(root)]
                else:
                    root_diameter = max(diameters.get(root, 0), 
                                    bottom_diameter.get(root,0)**power)

            sorted_vertices = list(traversal.post_order(g, root, complex=cid))
            for vid in sorted_vertices:
                if vid in diameters:
                    continue

                children = [v for v in g.children(vid) if g.complex(v) == cid]
                children_diam = [diameters[v] for v in children if v in diameters]
                diam = sum(children_diam)


                if has_root_diameter and diam > root_diameter:
                    if error:
                        if max(children_diam) < root_diameter:
                            print "ONE children has a greater radius value than its root."
                            print children, children_diam
                        else:
                            print 'WARNING: The pipe model compute at %d for power=%f a too large diameter.'%(vid, power)
                            print '       -> decrease the power of the pipe model.'
                        print 'root ', root, 'root_diam ', root_diameter, 'current ', diam
                    error_vertex.append(new_map[vid])

                if diam > 0:
                    diameters[vid] = diam

                strand = sum(strands.get(v,0) for v in children)
                if strand > 0:
                    strands[vid] = strand
                elif diam == 0:
                    strands[vid] = 1

            # Solve the boundary condition
            # if there are a bottom diam on root
            
            # check
            for vid in sorted_vertices:
                assert vid in strands or vid in diameters

            if has_root_diameter:
                #if len(sorted_vertices) == 1:
                #    diameters[root] = root_diameter
                #    continue

                delta_diameter = root_diameter - diameters.get(root,0)

                if delta_diameter < epsilon:
                    # compute strands default radius
                    # Add diameter only at the branching where 
                    # Select only the vertices which do not have a diam value.
                    strands_diameter = default_diameter
                    vtxs = [v for v in sorted_vertices if v in strands and v not in diameters]

                    for vid in vtxs:
                        s = strands[vid]
                        diameters[vid] = strands_diameter * s

                else:
                    # d**2 = sum(d**2) + sum(strand_diameter**2) = n * cst_strand_diameter**2
                    n = strands.get(root,0)
                    if n > 0:
                        strands_diameter = delta_diameter / n
                        vtxs = [v for v in sorted_vertices if v in strands]
                        for vid in vtxs:
                            diameters[vid] = diameters.get(vid, 0) + strands[vid] * strands_diameter
                    
            else:
                # Compute the total number of strands for the mtg
                nb_leaves = len([v for v in g.vertices(scale=2) if g.is_leaf(v)])
                if root not in diameters:
                    strands_diameter = default_diameter
                elif root not in strands:
                    continue
                else:
                    strands_diameter = diameters[root] / (nb_leaves - strands[root])
                    vtxs = [v for v in sorted_vertices if v in strands]
                    for vid in vtxs:
                        diameters[vid] = diameters.get(vid, 0) + strands[vid] * strands_diameter
                    

        # compute the final diameters
        factor = 1./power
        result = dict(( (new_map[v], d**factor) for v, d in diameters.iteritems()))

        self.error_vertex = error_vertex
        if error_vertex:
            print 'Warnings on diameter for %d vertices'%len(error_vertex)
        return result

    def advanced_algo_diameter2(self, power, default_diameter=None):
        """ 
        Compute the pipe model on the entire mtg.

        There are 4 cases:
            for each component:
                - traverse in a post_order way all the vertices
                    -  compute strands and diameter
                    - compute the difference at the root
                    - compute a diameter value for the strands

                - fix problem with wrong power value:
                    The diameter has to be decreasing.
                - if no value for the root, compute the total strands for the tree.
                - Then  divide by the defined radius values obtain from step 1.

        May be improved by a filtering pass.
        Select all the segment without ramification (linear) and interpolate the radius.
        """
        trees = self.decompose_radius()
        g = self.g
        max_scale = g.max_scale()
        dresser = self.dresser

        n = 0

        if default_diameter is None:
            default_diameter = 1 if not dresser.min_topdia else min(dresser.min_topdia.values())
            default_diameter *= 1./self.dresser.diameter_unit

        default_diameter = default_diameter**power


        strands = {}
        diameters = {}

        # update the defined properties with the new indices
        top_diameter = self.top_diameter
        bottom_diameter = self.bottom_diameter

        for k,td in top_diameter.iteritems():
            if g.scale(k) == max_scale:
                diameters[k] = td**power
        ###
        error_vertex = []
        # For each independant sub_systems
        
        for tree in trees.itervalues():
            # traverse the tree in a post_order way only for all vid in cid
            root = tree.root
            pid = g.parent(root)
            has_root_diameter = root in bottom_diameter or pid in diameters or g.parent(pid) in diameters
            strands.clear()
            if has_root_diameter:
                if pid in diameters:
                    root_diameter = diameters[pid]
                else:
                    root_diameter = max(diameters.get(g.parent(pid), 0), 
                                    bottom_diameter.get(root,0)**power)

            for vid in traversal.post_order(tree, root):
                assert vid not in diameters

                children_diam = [diameters[v] for v in g.children(vid) if v in diameters]
                diam = sum(children_diam)

                if has_root_diameter and diam > root_diameter:
                    if error:
                        if max(children_diam) < root_diameter:
                            print "ONE children has a greater radius value than its root."
                            print list(g.children(vid)), children_diam
                        else:
                            print 'WARNING: The pipe model compute at %d for power=%f a too large diameter.'%(vid, power)
                            print '       -> decrease the power of the pipe model.'
                        print 'root ', root, 'root_diam ', root_diameter, 'current ', diam
                    error_vertex.append(vid)

                if diam > 0:
                    diameters[vid] = diam

                strand = sum(strands.get(v,0) for v in g.children(vid))
                if strand > 0:
                    strands[vid] = strand
                elif diam == 0:
                    strands[vid] = 1

            # Solve the boundary condition
            # if there are a bottom diam on root
            
            if has_root_diameter:

                delta_diameter = root_diameter - diameters.get(root,0)

                if delta_diameter < epsilon:
                    # compute strands default radius
                    # Add diameter only at the branching where 
                    # Select only the vertices which do not have a diam value.
                    strands_diameter = default_diameter
                    for vid, nb_strands in strands.iteritems():
                        if vid not in diameters:
                            diameters[vid]= nb_strands * strands_diameter

                else:
                    # d**2 = sum(d**2) + sum(strand_diameter**2) = n * cst_strand_diameter**2
                    n = strands.get(root,0)
                    if n > 0:
                        strands_diameter = delta_diameter / n
                        for vid, nb_strands in strands.iteritems():
                            diameters[vid] = diameters.get(vid,0) + nb_strands * strands_diameter
                    
            else:
                n+=1
                # Compute the total number of strands for the mtg
                if strands.get(root,0)==0:
                    assert not bool(strands)
                    assert root in diameters
                    continue
                
                if root not in diameters:
                    strands_diameter = default_diameter
                else:
                    nb_leaves = len([v for v in traversal.pre_order2(g, root) if g.is_leaf(v)])
                    strands_diameter = diameters[root] / (nb_leaves - strands[root])

                for vid, nb_strands in strands.iteritems():
                    diameters[vid] = diameters.get(vid,0) + nb_strands * strands_diameter
                    

        # compute the final diameters
        factor = 1./power
        for v, d in diameters.iteritems():
            diameters[v] = d**factor

        self.error_vertex = error_vertex
        if error_vertex:
            print 'Warnings on diameter for %d vertices'%len(error_vertex)

        return diameters



    def build_mtg_from_radius(self):
        """ Decompose the tree (mtg at finest scale) into sub systems
        by creating complex which do not have interior nodes with a given values.
        Every complex have a defined frontier or are free.
        """
        g = self.g

        max_scale = g.max_scale()
        tree_root = g.roots(scale=max_scale).next()

        colors = {}
        tv = colors[2] = list(traversal.pre_order(g, tree_root))

        bd = self.bottom_diameter
        td = self.top_diameter

        
        complex = [v for v in tv if  (v == tree_root) or ((v in bd or g.parent(v) in td) and v not in td) ]

        colors[1] = complex
        
        mtg, new_map = colored_tree(g, colors)

        mtg_root = mtg.roots(scale=1).next()

        label = mtg.property('label')
        for v in mtg.vertices(scale=1):
            label[v] = 'R'+str(v)

        return mtg, new_map

    def decompose_radius(self):
        """ Decompose the tree (mtg at finest scale) into sub trees which contains
        all the free nodes (nodes without radius).
        by creating complex which do not have interior nodes with a given values.
        Every tree have a defined frontier or are free.
        """
        g = self.g
        bd = self.bottom_diameter
        td = self.top_diameter

        tree_id = {}
        trees = {}
        max_scale = g.max_scale()
        for tree_root in g.roots(scale=max_scale):
            for vid in traversal.pre_order(g, tree_root):
                if vid not in td:
                    pid = g.parent(vid)
                    if pid in tree_id:
                        tree = trees[tree_id[pid]]
                        tree.add_child(pid, vid)
                    else:
                        tree = PropertyTree(root=vid) 
                        trees[vid] = tree
                    tree_id[vid] = tree.root

        return trees

    #--------------------------------------------------------------------------------------
    #  algorithms with points
    #--------------------------------------------------------------------------------------

    #--------------------------------------------------------------------------------------
    #  algorithms with Length
    #--------------------------------------------------------------------------------------
    def algo_length(self, default_length=None):
        """
        Compute the length of each vertex.
        The length of a complex is the sum of the length of its components.
        Length can be computed from points or is given as a property.
        """
        # Check if points are defined
        # 1. points not defined
        if not self.points:
            return self.algo_length_without_points(default_length=default_length)
        else:
            pass
        return {}

    def algo_length_without_points(self, default_length=None):

        g = self.g
        length = self.length
        min_length = self.dresser.min_length.copy()
        unit = self.dresser.length_unit

        if min_length and not default_length: 
            default_lenght = min(min_length.values())
        else:
            default_length = default_length if default_length else 1

        _length = {}
        _unknows = {}

        max_scale = g.max_scale()

        # Traverse all the scales.
        # in  bottom up to propaate values and unknows
        for scale in range(max_scale, 1, -1):
            for vid in g.vertices(scale=scale):
                cid = g.complex(vid)
                name = g.class_name(vid)

                if vid in length:
                    _length[cid] = _length.get(cid,0) + length[vid]

                elif vid in _length:
                    _length[cid] = _length.get(cid,0) + _length[vid]

                elif vid in _unknows:
                    d = _unknows[vid]
                    complex_unknow = _unknows.setdefault(cid,{})
                    for name, x in d.iteritems():
                        complex_unknow[name] = d.get(name) + x

                else:
                    if name not in min_length:
                        name = 'default'
                    _unknows[cid][name] = _unknows.setdefault(cid,{name:0}).get(name,0) + 1
            
        print _length, _unknows
        # Solve the equations in top down.
        marked = {}
        class Visitor:
            def pre_order(self, vid):
                if vid in marked or vid in length:
                    return False
                else: 
                    return True

            def post_order(self, vid):
                pass

        visitor = Visitor()

        # A possible alternative is to add a weight depending on the ClassName.
        for vid in length.keys():
            if vid not in _unknows:
                continue
            n = sum(_unknows.get(vid).values())
            x = (length[vid] - _length.get(vid,0)) / float(n)

            for v in traversal.pre_order_in_scale(g,vid, visitor):
                if v not in length:
                    print v
                    length[v] = _length.get(v,0) + x * sum(_unknows.get(vid).values())

        # Solve all the others without length

        for root in g.roots(scale=1):
            for v in traversal.pre_order_in_scale(g, root, visitor):
                if v not in length:
                    l = _length.get(v,0) 
                    for name, weight in _unknows.get(v,{}).iteritems():
                        l+= weight * min_length.get(name, default_length) / unit
                    length[v] = l

        return length



    #--------------------------------------------------------------------------------------
    #  Phyllotaxy algorithms
    #--------------------------------------------------------------------------------------

###########################################################################################

def iter_order(g, v, edge_type = None):
    ''' Iter on a tree by considering first 
    all the vertices of the axe at the first order,
    then the vertices at the second order and so on.
    '''
    pass

def compute_axes(g, v, fixed_points, origin):
    marked = {}
    axes = {}
    others = {}
    for vid in traversal.post_order(g,v):
        if vid in marked:
            continue
        
        _axe = list(simple_axe(g,vid, marked, fixed_points))
        _axe.reverse()
        
        _axe, other = zip(*_axe)
        axes.setdefault(g.order(_axe[0]),[]).append(list(_axe))
        others.setdefault(g.order(_axe[0]),[]).append(list(other))
        
    orders = axes.keys().sort()
    for order in axes:
        for i, axe in enumerate(axes[order]):
            other = others[order][i]
            _axe = zip(axe, other)
            if order == 0: 
                new_points = compute_missing_points(g, _axe, fixed_points, origin=origin)
            else:
                new_points = compute_missing_points(g, _axe, fixed_points)
            fixed_points.update(new_points)

    return axes


def simple_axe(g, v, marked, fixed_points):
    edge_type = g.property('edge_type')
    
    while v is not None:
        if v in fixed_points:
            yield v, True
        else: 
            yield v, False
        
        assert v not in marked
        marked[v] = True
        
        if g.parent(v) is None or edge_type[v] == '+':
            break
        v = g.parent(v)

def compute_missing_points(g, axe, fixed_points, origin=None):
    """
    axe is a list of tuple containing both vid and a boolean indicated if
    a point is defined on a vertex.
    return a dict of {id:point}.
    """
    new_points = {} # list of points
    interval = [] # list of the different interval with missing values
    first = False
    last = False
    prev = -1 # previous id with a defined point value
    current = [] # list of points to define an interval

    begin = True 

    for vid, defined in axe:
        if begin:
            first = not defined
            begin = False

        if not defined:
            if (not current) and (prev != -1) :
                current.append(prev)
            current.append(vid)
        else:
            prev = vid
            if current:
                current.append(vid)
                interval.append(current)
                current = []
    if current:
        interval.append(current)
        last = True

    i0 = []
    i1 = []
    if first:
        i0 = interval[0]
        del interval[0]
    if last and interval:
        i1 = interval[-1]
        del interval[-1]

    for inter in interval:
        n = len(inter)-1
        v1, v2 = inter[0], inter[-1]
        p1, p2 = fixed_points[v1], fixed_points[v2]
        pt12 = Vector3(*p2) -Vector3(*p1)
        step = pt12 / n

        for i, v in enumerate(inter):
            if i == 0:
                pt = Vector3(*p1)
            elif i == n:
                continue
            else:
                pt = pt + step
                new_points[v] = pt
        
    # Management of first and last interval.
    # It is a silly algorithm.
    if i0 and (i0[-1], True) in axe:
        if g.parent(i0[0]) in fixed_points:
            origin = fixed_points[g.parent(i0[0])]

        if origin :
            inter = i0
            # The first point do not belong to the interval
            n = len(inter) 

            v2 = inter[-1]
            p1, p2 = Vector3(*origin), fixed_points[v2]
            pt12 = Vector3(*p2) -Vector3(*p1)
            step = pt12 / n
            pt = p1
            for i, v in enumerate(inter):
                if i+1 != n:
                    pt = pt + step
                    new_points[v] = pt

        else:
            """
            # We must compute the min disance between the axe and its parent
            v0 = i0[-1]

            if (v0, True) in axe:
                
                index0 = axe.index((v0,True))
                if index0+1 < len(axe):
                    v1, defined = axe[index0+1]
                    if defined:
                        p2 = Vector3(*fixed_points[v1])
                    else:
                        p2 = new_points.get(v1)
                
                    if p2:
                        p1 = Vector3(*fixed_points[v0])
                        pt21 = Vector3(*p2) -Vector3(*p1)
                        n = len(i0)-1
                        for i, v in enumerate(i0[:-1]):
                            index = n-i
                            pt = p1 + pt21*(index/n)
                            #new_points[v] = pt
                        
                            if v == 2503:
                                print 2, v, p1, p2, step, pt21 
                                if g.parent(v) in fixed_points:
                                    print step - (p1-fixed_points[g.parent(v)])
            """
            print 'TODO : point for ', i0[0]

    if i1 and (i1 != i0):
        v1 = i1[0]
        v0 = g.parent(v1)
        p1 = fixed_points.get(v0,new_points.get(v0))
        if p1 :
            p1 = Vector3(*p1)
            p2 = fixed_points[v1]
            p2 = Vector3(*p2)
            pt12 = p2 -p1
            n = len(i1)-1
            for i, v in enumerate(i1[1:]):
                pt = p2 + pt12*(i+1)
                new_points[v] = pt
 
    return new_points

def compute_radius(g, v, last_radius):
    all_r2 = {}
    for vid in traversal.post_order(g, v):
        r2 = max(sum([all_r2[c] for c in g.children(vid)]), last_radius)
        all_r2[vid] = r2
    for k, v in all_r2.iteritems():
        all_r2[k] = sqrt(v)
    return all_r2

def compute_diameter(g, v, radius, default_value):

    all_r = {}
    unknow= []
    edge_type = g.property('edge_type')
    for vid in traversal.post_order(g, v):
        if vid in radius:
            if radius[vid] < default_value:
                all_r[vid] = default_value
            else:
                all_r[vid] = radius[vid]
        elif g.is_leaf(vid):
            v = g.complex(vid)
            while v:
                if v in radius:
                    all_r[vid] = radius[v]
                    break
                else:
                    v = g.complex(v)
            else:
                all_r[vid] = default_value
        else:
            # pipe model (r_parent **n = sum r_child**n with r ==2)
            all_r[vid] = sqrt(sum([all_r[c]**2 for c in g.children(vid)]))

    return all_r

def build_scene(g, origin, axes, points, diameters, default_radius, option='axe'):


    scene = Scene()
    section = Polyline2D.Circle(0.5,10)

    polylines = []
    radius_law = []
    scale = g.max_scale()

    rad = diameters
    if option == 'cylinder':
        for vid in points :
            if g.scale(vid) != scale:
                continue
            parent = g.parent(vid)
            if parent is None:
                point_parent = origin
            elif parent in points:
                point_parent = points[parent]

            poly = [point_parent, points[vid]]
            curve = Polyline(poly)

            if vid not in rad or parent not in rad:
                rad_vid = rad.get(vid, default_radius)
                rad_parent = rad.get(parent, rad_vid)
                radius = [[rad_parent]*2, [rad_vid]*2]
                shape = Shape(Extrusion(curve, section, radius), Material(Color3(255,0,0)))
                shape.id = vid
                scene += shape
            else:
                rad_vid = rad.get(vid, 1)
                rad_parent = rad.get(parent, rad_vid)
                radius = [[rad_parent]*2, [rad_vid]*2]
                shape = Shape(Extrusion(curve, section, radius))
                shape.id = vid
                scene += shape

        return scene

    for order in axes:
        for axe in axes[order]:
            parent = g.parent(axe[0])
            if  order > 0 and parent and (parent in points):
                axe.insert(0,parent)
            elif order == 0:
                axe.insert(0, axe[0])
            poly = [points[vid] for vid in axe if vid in points]
            if order == 0:
                poly[0] = origin

            # Delete null segments
            eps = 1
            curve = Polyline(poly)

            radius = [[rad.get(vid, 1.)]*2 for vid in axe if vid in points]
            if len(radius)>1:
                radius[0] = radius[1]

                curve, radius = clean_curve(curve, radius)

                scene += Extrusion(curve, section, radius)

    return scene

def debug(g, scene, points, order, scale=3, color=(255,0,0)):
    c = Material(Color3(*color))
    sphere = Sphere(radius=30)
    for id, pt in points.iteritems():
        if g.order(id) == order and g.scale(id) == scale:
            scene+= Shape(Translated(pt,sphere), c)
    return scene
    

def clean_curve(poly, radius):
    """ Remove too small elements.
    """
    pts = poly.pointList
    n = len(pts)

    length = poly.getLength()
    mean = length / (n-1)

    eps = mean/100.
    eps2 = eps**2

    index = [True]*n

    new_poly = [pts[0]]
    new_radius = [radius[0]]

    for i in range(1,n):
         p12= pts[i] - pts[i-1]
         if p12.__normSquared__() > eps2:
            new_poly.append(pts[i])
            new_radius.append(radius[i])

    return Polyline(new_poly), new_radius



