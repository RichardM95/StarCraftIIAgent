"""Deterministic art/layout recipe for the Verdant Reliquary test battlefield.

This module produces arrays and placements only. Terrain, object writes and
recovery are handled by the application's transaction layer.
"""
from __future__ import annotations

import math
import numpy as np


PALETTE = ['BelShirDirtLight','BelShirDirtDark','BelShirBrush','BelShirGrassLight',
           'BelShirGrassDark','BelShirSmallTiles','BelShirBricksSmall','BelShirBricksLarge']
STARTS = [[24.0,58.0],[104.0,58.0]]
NORTH = [(24,58),(29,72),(40,85),(53,90),(66,91),(80,87),(95,76),(104,58)]
SOUTH = [(x,116-y) for x,y in NORTH]
LANDMARKS = [(64,98),(64,18),(43,69),(85,47)]


def _curve(points, subdivisions=5):
    points=np.asarray(points,dtype=float)
    padded=np.concatenate([points[:1],points,points[-1:]])
    result=[]
    for index in range(1,len(padded)-2):
        p0,p1,p2,p3=padded[index-1:index+3]
        for t in np.linspace(0,1,subdivisions,endpoint=False):
            result.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
    return np.asarray([*result,points[-1]])


def _distance(x,y,points):
    result=np.full(np.broadcast_shapes(x.shape,y.shape),np.inf,dtype=np.float32)
    for a,b in zip(points[:-1],points[1:]):
        dx,dy=b-a
        t=np.clip(((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy),0,1)
        result=np.minimum(result,np.hypot(x-(a[0]+t*dx),y-(a[1]+t*dy)))
    return result


def _smooth(a,b,v):
    t=np.clip((v-a)/(b-a),0,1)
    return t*t*(3-2*t)


def geometry(x,y):
    main=np.abs(y-(58+1.8*np.sin((x-24)*np.pi/80)))
    flanks=np.minimum(_distance(x,y,_curve(NORTH)),_distance(x,y,_curve(SOUTH)))
    center=np.hypot(x-64,y-58)
    bases=np.minimum(np.hypot(x-24,y-58),np.hypot(x-104,y-58))
    clearance=np.minimum.reduce(np.broadcast_arrays(main-6,flanks-4,center-15,bases-10))
    return main,flanks,center,bases,clearance


def design_fields(seed=11011):
    """128 native tiles; broad center, forest flanks, two assembly clearings."""
    vy,vx=np.mgrid[:129,:129].astype(np.float32)
    main,flanks,center,bases,clearance=geometry(vx,vy)
    hills=.6*np.sin(vx*.12+.6)*np.sin(vy*.105)+.18*np.sin(vx*.32-vy*.21)
    heights=7.65+hills+.55*_smooth(4,17,clearance)
    heights-=1.05*np.exp(-(center/20)**2)
    heights+=.25*np.exp(-((vx-43)**2+(vy-69)**2)/50)
    heights+=.25*np.exp(-((vx-85)**2+(vy-47)**2)/50)
    road=np.exp(-(main/5.5)**4)
    heights=heights*(1-.75*road)+(7.15+.25*np.cos((vx-24)*np.pi/80))*.75*road
    base_blend=1-_smooth(8,12,bases)
    heights=heights*(1-base_blend)+7.6*base_blend
    # Blend back to the source boundary so unknown exterior cell data remains sensible.
    edge=np.minimum.reduce([vx,vy,128-vx,128-vy])
    heights=8+(np.clip(heights,6.45,8.85)-8)*_smooth(2,8,edge)
    py,px=np.mgrid[:1024,:1024].astype(np.float32)
    x=(px+.5)/8;y=(py+.5)/8
    main,flanks,center,bases,clearance=geometry(x,y)
    noise=.5*np.sin(x*.31+y*.17)+.3*np.sin(x*.81-y*.47)+.2*np.cos(x*1.23+y*.93)
    weights=np.zeros((8,1024,1024),dtype=np.float32)
    weights[3]=.55+.25*np.sin(x*.065)*np.cos(y*.09)
    weights[4]=.30+.20*_smooth(2,13,clearance)
    weights[2]=.15+.12*(noise+1)
    weights/=weights.sum(axis=0)
    def overlay(slot,alpha):
        nonlocal weights
        alpha=np.clip(alpha,0,1)
        weights*=1-alpha
        weights[slot]+=alpha
    road=1-_smooth(4.8,7.8,main+.45*noise)
    flank=1-_smooth(2.7,5.0,flanks+.65*noise)
    base=1-_smooth(8,11,bases+.4*noise)
    overlay(1,np.maximum(flank*.68,road*.34))
    overlay(0,np.maximum.reduce([road*.90,base*.90,flank*.50]))
    # The plaza has a worn mosaic core and a mossy broken border, with open lanes.
    plaza=1-_smooth(12.8,15.8,center+.5*noise)
    overlay(5,plaza*.94)
    ring=(1-_smooth(.6,1.7,np.abs(center-16.6)+.22*noise))
    overlay(7,ring*.83)
    inlay=(1-_smooth(.3,.8,np.abs(center-9.8)))*plaza
    overlay(6,inlay*.72)
    # Small ruins receive individually shaped foundations; no carpet of stone.
    for cx,cy in LANDMARKS:
        dist=np.hypot((x-cx)*1.1,y-cy)
        overlay(6,(1-_smooth(3.5,6.0,dist+.35*noise))*.86)
    overlay(2,np.clip((noise-.35)*.25,0,.13)*(1-plaza))
    # Keep only the two strongest materials at each pixel, then quantize to 15.
    top=np.argpartition(weights,-2,axis=0)[-2:]
    selected=np.take_along_axis(weights,top,axis=0)
    ratio=selected[0]/selected.sum(axis=0)
    first=np.rint(ratio*15).astype('u1')
    quantized=np.zeros_like(weights,dtype='u1')
    np.put_along_axis(quantized,top[0:1],first[None],axis=0)
    np.put_along_axis(quantized,top[1:2],(15-first)[None],axis=0)
    ty,tx=np.mgrid[:128,:128].astype(float);tx+=.5;ty+=.5
    _,_,_,_,cell_clearance=geometry(tx,ty)
    boundary=(tx<14)|(tx>114)|(ty<12)|(ty>104)
    ground=np.where(boundary,255,0).astype('u1')
    building=ground.copy()
    # Assembly pads remain buildable; forest/backdrops are scenery.
    building[(cell_clearance>2)&~boundary]=255
    return {'heights':heights,'texture_weights':quantized,'ground_mask':ground,
            'building_mask':building,'seed':seed,'cell_clearance':cell_clearance}


def design_objects(palette, seed=11011):
    rng=np.random.default_rng(seed)
    kinds={item['id']:item for item in palette['doodads']}
    objects=[];reserved=[]
    gy,gx=np.mgrid[:129,:129].astype(float)
    clearance_grid=geometry(gx,gy)[-1]
    from .spatial_batch import sample_height
    def clear(x,y):
        return sample_height(clearance_grid,float(x),float(y))
    def place(name,x,y,scale=1.0,rotation=None,offset=0.0,category='detail',radius=.5):
        entry=kinds[name]
        available=entry.get('verified_variations')
        if not available:
            raise ValueError(f'{name}: missing verified model variations')
        variation=int(rng.choice([item['object_variation'] for item in available]))
        attrs={'Type':name,'Variation':str(variation),'Position':f'{x:.6f},{y:.6f},{offset:.6f}',
               'Rotation':f'{rng.uniform(0,math.tau) if rotation is None else rotation:.6f}',
               'Scale':f'{scale:.6f},{scale:.6f},{scale*rng.uniform(.94,1.06):.6f}'}
        objects.append({'kind':'doodad','attributes':attrs,'category':category,'radius':radius})
        reserved.append((x,y,radius))
    # Two distant gateways frame the view without occupying a traverse route.
    for cx,cy in [(64,98),(64,18)]:
        angle=0 if cy>58 else math.pi
        place('TempleArch',cx,cy,1.05,angle,-.1,'landmark',3.4)
        for sign in (-1,1):
            place('TempleStatue',cx+sign*7,cy,.9,angle,-.08,'landmark',2.5)
            place('TempleColumnWalls',cx+sign*10,cy-1 if cy>58 else cy+1,.85,angle,-.07,'ruin',1.7)
    # Columns around the plaza have deliberately large openings on every route.
    for angle in [40,65,110,140,220,245,290,320]:
        a=math.radians(angle);x=64+19.7*math.cos(a);y=58+19.7*math.sin(a)
        if clear(x,y)>1.5:
            place('TempleColumn',x,y,rng.uniform(.8,1.2),a,-.08,'ruin',1.2)
            place('TempleBricks',x+1.4,y-.7,.75,None,-.04,'detail',.4)
    for cx,cy in [(43,69),(85,47)]:
        place('TempleStatue',cx,cy,1.05,None,-.12,'landmark',2.4)
        for dx,dy in [(-3,2),(3,1),(-2,-3)]:
            place('TempleDebris',cx+dx,cy+dy,rng.uniform(.65,.95),None,-.10,'ruin',1.0)
    # Forest clusters, with deliberate negative space along all three routes.
    centers=[(20,25),(28,91),(43,102),(89,100),(108,92),(109,25),(89,15),
             (38,38),(48,77),(80,38),(89,75),(19,76),(110,43),(63,9),(7,58),(121,58)]
    for cx,cy in centers:
        accepted=0
        for _ in range(160):
            if accepted>=11:break
            x=cx+rng.normal(0,5);y=cy+rng.normal(0,4)
            if not (5<x<123 and 5<y<113):continue
            if clear(x,y)<4.4:continue
            if any(math.hypot(x-a,y-b)<1.9+r for a,b,r in reserved):continue
            name='BelShirTree' if rng.random()<.83 else 'BelShirCanopyTrees'
            scale=float(rng.uniform(.78,1.20) if name=='BelShirTree' else rng.uniform(.55,.78))
            place(name,x,y,scale,None,-.06,'tree',1.35)
            accepted+=1
    for _ in range(800):
        x=float(rng.uniform(9,119));y=float(rng.uniform(9,107))
        clearance=clear(x,y)
        if clearance<2.7:continue
        if any(math.hypot(x-a,y-b)<1.1+r for a,b,r in reserved):continue
        name='RockLarge' if rng.random()<.45 else 'Rock'
        place(name,x,y,float(rng.uniform(.7,1.45)),None,-.12,'rock',1.25 if name=='RockLarge' else .8)
        if sum(o['category']=='rock' for o in objects)>=100:break
    for _ in range(5500):
        x=float(rng.uniform(12,116));y=float(rng.uniform(12,104))
        clearance=clear(x,y)
        if clearance<1.25:continue
        density=.55+.35*math.sin(x*.26)*math.cos(y*.22)
        if rng.random()>density:continue
        if any(math.hypot(x-a,y-b)<.35+r*.72 for a,b,r in reserved):continue
        name=str(rng.choice(['BelShirUnderbrush','BelShirFoliage','BelShirShrub','BelShirFlowers',
                             'BelShirAlienShrubs','RockSmall'],p=[.22,.18,.22,.17,.12,.09]))
        place(name,x,y,float(rng.uniform(.48,.9)),None,-.025,'foliage',.36)
        if sum(o['category']=='foliage' for o in objects)>=420:break
    for i,(x,y) in enumerate(STARTS):
        objects.append({'kind':'point','attributes':{'Type':'StartLoc' if i==0 else 'Normal','Position':f'{x},{y},0',
                        'Scale':'1,1,1','Rotation':'0','Color':'0,0,0,0'},'category':'start','radius':0})
    return objects


def obstacle_mask(fields,objects):
    """Conservative painted scenery footprints, not the engine's pathing mesh."""
    y,x=np.mgrid[:128,:128];x=x+.5;y=y+.5
    mask=fields['ground_mask'].copy()
    for item in objects:
        if item['category'] in {'start','foliage','detail'}:continue
        px,py,_=map(float,item['attributes']['Position'].split(','))
        radius=item['radius']
        mask[np.hypot(x-px,y-py)<=radius]=255
    return mask
