"""Versioned, lossless terrain readers and bounded mutation planners.

Binary layout evidence is recorded in docs/TERRAIN-FORMATS.md.  These readers
never silently substitute a grid for a missing/unknown component.  Offline
height/pathing previews are diagnostics, not engine render/pathfinding proof.
"""
from __future__ import annotations

import math
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .errors import SC2Error


def _grid(data, magic, version, header, stride, width_offset=8):
    if len(data) < header or data[:4] != magic or struct.unpack_from("<I", data, 4)[0] != version:
        raise SC2Error("unsupported_terrain_format", "地形组件版本未验证", magic=repr(data[:4]))
    w, h = struct.unpack_from("<II", data, width_offset)
    if not 1 <= w <= 4097 or not 1 <= h <= 4097 or len(data) != header + w*h*stride:
        raise SC2Error("invalid_terrain_size", "地形组件尺寸或长度不符", width=w, height=h, bytes=len(data))
    return w, h


class Terrain:
    def __init__(self, root: Path, overrides=None):
        self.root = Path(root)
        self.overrides = overrides or {}
        self.raw = {}
        def read(name):
            p = self.root / name
            b = self.overrides.get(name, p.read_bytes() if p.exists() else None)
            if b is None:
                raise SC2Error("terrain_component_missing", "缺少地形组件", file=name)
            self.raw[name] = b
            return b
        self.xml = read("t3Terrain.xml")
        self.tree = ET.fromstring(self.xml)
        if self.tree.tag != "terrain" or self.tree.get("version") != "115":
            raise SC2Error("unsupported_terrain_format", "仅支持已采样的 terrain XML v115")
        self.meta = self.tree.find("heightMap")
        if self.meta is None:
            raise SC2Error("invalid_terrain_xml", "缺少 heightMap")
        self.width, self.height = map(int, self.meta.get("dim", "").split())
        self.tile_width, self.tile_height = self.width-1, self.height-1
        q = self.meta.find("vertData")
        if q is None:
            raise SC2Error("invalid_terrain_xml", "缺少 vertData")
        self.bias, self.scale = float(q.get("quantizeBias")), float(q.get("quantizeScale"))
        if not math.isfinite(self.bias) or not math.isfinite(self.scale) or self.scale <= 0:
            raise SC2Error("invalid_quantization", "高度量化参数无效")
        b = read("t3HeightMap")
        if _grid(b, b"HMAP", 101, 32, 6) != (self.width, self.height):
            raise SC2Error("terrain_dimension_mismatch", "HMAP 与 XML 尺寸不一致")
        self.vertices = np.frombuffer(b, dtype="<u2", offset=32).reshape(self.height,self.width,3).copy()
        b = read("t3SyncHeightMap")
        if _grid(b, b"SMAP", 102, 64, 4) != (self.width,self.height):
            raise SC2Error("terrain_dimension_mismatch", "SMAP 与 XML 尺寸不一致")
        self.sync = np.frombuffer(b,dtype="<i2",offset=64).reshape(self.height,self.width,2).copy()
        b = read("t3SyncCliffLevel")
        if _grid(b,b"CLIF",100,32,2) != (self.tile_width,self.tile_height):
            raise SC2Error("terrain_dimension_mismatch", "CLIF 尺寸不一致")
        self.cliffs = np.frombuffer(b,dtype="<u2",offset=32).reshape(self.tile_height,self.tile_width).copy()
        b = read("t3CellFlags")
        if _grid(b,b"LFCT",102,32,1,24) != (self.tile_width,self.tile_height):
            raise SC2Error("terrain_dimension_mismatch", "CellFlags 尺寸不一致")
        self.flags = np.frombuffer(b,dtype="u1",offset=32).reshape(self.tile_height,self.tile_width).copy()
        self.textures = {int(x.get("i")): x.get("name") for x in self.meta.findall("textureList/texture") if x.get("name")}
        self._read = read

    @property
    def heights(self):
        return self.sync[:,:,0].astype(float)/256.0

    @property
    def detailed_heights(self):
        return (self.vertices[:,:,0].astype(float)+self.vertices[:,:,1].astype(float))*self.scale-2*self.bias

    def rect(self, values, vertices=False):
        if len(values) != 4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
            raise SC2Error("invalid_rectangle", "选区必须为有限数值 [x0,y0,x1,y1]")
        if any(v != int(v) for v in values):
            raise SC2Error("invalid_rectangle", "当前选区需对齐整格坐标")
        x0,y0,x1,y1 = map(int,values)
        if not 0 <= x0 < x1 <= self.tile_width or not 0 <= y0 < y1 <= self.tile_height:
            raise SC2Error("rectangle_outside_map", "选区越界或为空")
        return x0,y0,x1+(1 if vertices else 0),y1+(1 if vertices else 0)

    def summary(self):
        difference = np.abs(self.detailed_heights-self.heights)
        return {"terrain_version": self.tree.get("version"), "tileset": self.meta.get("tileSet"),
                "vertex_dimensions": [self.width,self.height], "tile_dimensions": [self.tile_width,self.tile_height],
                "height_range": [float(self.heights.min()),float(self.heights.max())],
                "cliff_levels": np.unique(self.cliffs >> 6).tolist(), "textures": self.textures,
                "ramps": [dict(x.attrib) for x in self.meta.findall("rampList/ramp")],
                "quantization": {"bias": self.bias,"scale": self.scale},
                "height_layer_difference": {"median":float(np.median(difference)),"max":float(difference.max()),
                                           "note":"同步高度可能含引擎平滑，不要求与详细高度逐点相同"},
                "evidence": {"binary":"sample_checked", "editor":"not_run", "runtime":"not_run"}}

    def texture_weights(self):
        b = self._read("t3TextureMasks")
        w,h = _grid(b,b"MASK",102,64,4,12)
        if (w,h) != (self.tile_width*8,self.tile_height*8) or struct.unpack_from("<I",b,8)[0] != 0 or w%64 or h%64:
            raise SC2Error("unsupported_texture_layout", "仅支持单套八层纹理遮罩")
        packed = np.frombuffer(b,dtype="u1",offset=64).reshape(8,h,w//2)
        result = np.empty((8,h,w),dtype="u1")
        result[:,:,0::2] = packed & 15
        result[:,:,1::2] = packed >> 4
        # Each layer is stored as row-major 64x64 pixel blocks, not one large
        # row-major image. Verified against the synchronized tile texture layer.
        return result.reshape(8,h//64,w//64,64,64).transpose(0,1,3,2,4).reshape(8,h,w)

    def encode_texture_weights(self, weights):
        _,h,w=weights.shape
        blocked=weights.reshape(8,h//64,64,w//64,64).transpose(0,1,3,2,4).reshape(8,h,w)
        packed=blocked[:,:,0::2] | (blocked[:,:,1::2]<<4)
        return self.raw["t3TextureMasks"][:64]+packed.tobytes()

    def sync_textures(self):
        b = self._read("t3SyncTextureInfo")
        if len(b)<20 or b[:4]!=b"RTXT" or struct.unpack_from("<I",b,4)[0]!=101:
            raise SC2Error("unsupported_texture_layout", "RTXT 版本未验证")
        w,h,count = struct.unpack_from("<III",b,8)
        if (w,h)!=(self.tile_width,self.tile_height) or count!=1:
            raise SC2Error("unsupported_texture_layout", "RTXT 多纹理集尚未验证")
        offset=20
        names=[]
        try:
            for _ in range(8):
                end=b.index(b"\0",offset);names.append(b[offset:end].decode("utf-8"));offset=end+1
        except (ValueError,UnicodeError) as exc:
            raise SC2Error("invalid_texture_table", "RTXT 纹理名称损坏") from exc
        if len(b)!=offset+w*h*8:
            raise SC2Error("unsupported_texture_layout", "RTXT 载荷长度未验证")
        return names,offset,np.frombuffer(b,dtype="<u8",offset=offset).reshape(h,w).copy()

    def pathing_layer(self, name):
        b=self._read(name)
        if len(b)!=4+self.tile_width*self.tile_height or struct.unpack_from("<I",b)[0]!=self.tile_width*self.tile_height*8:
            raise SC2Error("unsupported_pathing_layout", "绘制通行层格式未验证", file=name)
        return np.frombuffer(b,dtype="u1",offset=4).reshape(self.tile_height,self.tile_width).copy()


def plan_terrain(root: Path, operations: list[dict]):
    if not operations or len(operations)>256:
        raise SC2Error("invalid_operations", "地形操作数量必须为 1 至 256")
    t=Terrain(root)
    changed={}
    for operation in operations:
        op=operation.get("op")
        if op in ("raise","set_height","smooth"):
            x0,y0,x1,y1=t.rect(operation.get("rect",[]),vertices=True)
            selection=t.heights[y0:y1,x0:x1].copy()
            if op=="smooth":
                iterations=operation.get("iterations",1)
                if not isinstance(iterations,int) or not 1<=iterations<=30:
                    raise SC2Error("invalid_iterations", "平滑次数需为 1 至 30")
                result=selection.copy()
                for _ in range(iterations):
                    p=np.pad(result,1,mode="edge")
                    result=(p[1:-1,1:-1]*4+p[:-2,1:-1]+p[2:,1:-1]+p[1:-1,:-2]+p[1:-1,2:])/8
            else:
                value=operation.get("value")
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>128:
                    raise SC2Error("invalid_height", "高度必须为有限数值")
                result=selection+value if op=="raise" else np.full_like(selection,value)
            # Adjust the editable base-height channel and synchronized height by the
            # same quantized delta; preserve terrain detail, cliff masks and residuals.
            delta=np.rint((result-selection)/t.scale).astype(np.int64)
            base=t.vertices[y0:y1,x0:x1,0].astype(np.int64)+delta
            sync=np.rint((selection+delta*t.scale)*256).astype(np.int64)
            if np.any(base<0) or np.any(base>65535) or np.any(sync<-32768) or np.any(sync>32767):
                raise SC2Error("height_out_of_range", "修改超出此地图的高度量化范围，拒绝全图重新量化")
            t.vertices[y0:y1,x0:x1,0]=base
            t.sync[y0:y1,x0:x1,0]=sync
            changed["t3HeightMap"]=t.raw["t3HeightMap"][:32]+t.vertices.tobytes()
            changed["t3SyncHeightMap"]=t.raw["t3SyncHeightMap"][:64]+t.sync.tobytes()
        elif op=="paint_texture":
            x0,y0,x1,y1=t.rect(operation.get("rect",[]))
            index=operation.get("texture")
            strength=operation.get("strength",1.0)
            if not isinstance(index,int) or index not in t.textures or index not in range(8):
                raise SC2Error("texture_unavailable", "纹理必须是当前地图已定义的 0 至 7 号槽位")
            if not isinstance(strength,(int,float)) or not math.isfinite(strength) or not 0<=strength<=1:
                raise SC2Error("invalid_strength", "纹理强度需在 0 至 1 之间")
            if "t3TextureMasks" in changed:
                t.overrides["t3TextureMasks"]=changed["t3TextureMasks"]
            if "t3SyncTextureInfo" in changed:
                t.overrides["t3SyncTextureInfo"]=changed["t3SyncTextureInfo"]
            weights=t.texture_weights()
            original_area=weights[:,y0*8:y1*8,x0*8:x1*8].copy()
            area=original_area.astype(float)
            if np.any(area.sum(axis=0)!=15):
                raise SC2Error("unsupported_texture_weights", "选区纹理权重和不为 15，拒绝猜测混合语义")
            area*=1-strength
            area[index]+=15*strength
            # Largest-remainder allocation preserves the exact sum of 15. Rounding
            # all channels independently can produce sums of 12 or 18 at seams.
            quantized=np.floor(area).astype("u1")
            remainder=15-quantized.sum(axis=0).astype(int)
            ranks=np.argsort(-(area-quantized),axis=0,kind="stable")
            for rank in range(8):
                increments=(remainder>rank).astype("u1")[None,:,:]
                np.put_along_axis(quantized,ranks[rank:rank+1],np.take_along_axis(quantized,ranks[rank:rank+1],axis=0)+increments,axis=0)
            weights[:,y0*8:y1*8,x0*8:x1*8]=quantized
            changed_tiles=np.any((original_area!=quantized).reshape(8,y1-y0,8,x1-x0,8),axis=(0,2,4))
            if not np.any(changed_tiles):
                continue
            changed["t3TextureMasks"]=t.encode_texture_weights(weights)
            names,offset,sync_tex=t.sync_textures()
            if any(t.textures.get(i,"")!=names[i] for i in range(8)):
                raise SC2Error("texture_table_mismatch", "XML 与 RTXT 纹理表不一致")
            dominant=weights.reshape(8,t.tile_height,8,t.tile_width,8).mean(axis=(2,4)).argmax(axis=0)
            view=sync_tex[y0:y1,x0:x1]
            view[changed_tiles]=dominant[y0:y1,x0:x1][changed_tiles]
            changed["t3SyncTextureInfo"]=t.raw["t3SyncTextureInfo"][:offset]+sync_tex.tobytes()
        elif op in ("block_ground","block_building","clear_ground_paint","clear_building_paint"):
            x0,y0,x1,y1=t.rect(operation.get("rect",[]))
            name="CellAttribute_Pnp" if "ground" in op else "CellAttribute_Pnb"
            if name in changed:
                t.overrides[name]=changed[name]
            layer=t.pathing_layer(name)
            layer[y0:y1,x0:x1]=0 if op.startswith("clear") else 255
            changed[name]=t.raw[name][:4]+layer.tobytes()
        else:
            raise SC2Error("unsupported_terrain_operation", "该地形操作尚未完成格式和编辑器验证", operation=op,
                           available=["raise","set_height","smooth","paint_texture","block_ground","block_building","clear_ground_paint","clear_building_paint"])
    return {k:v for k,v in changed.items() if v!=(root/k).read_bytes()}


def render_terrain(root: Path, destination: Path, overrides=None):
    t=Terrain(root,overrides)
    unavailable=[]
    destination.mkdir(parents=True,exist_ok=True)
    z=t.heights
    zn=(z-z.min())/max(float(np.ptp(z)),.001)
    color=np.stack([40+zn*150,65+zn*140,70+zn*115],axis=-1).astype("u1")
    gy,gx=np.gradient(z)
    lighting=np.clip(.85-.10*gx+.15*gy,.35,1.3)
    color=np.clip(color*lighting[:,:,None],0,255).astype("u1")
    base=Image.fromarray(np.flipud(color)).resize((720,600),Image.Resampling.NEAREST)
    draw=ImageDraw.Draw(base)
    draw.rectangle((0,0,720,25),fill="#17232c")
    draw.text((8,7),"OFFLINE HEIGHT PREVIEW | not an editor screenshot",fill="white")
    base.save(destination/"height.png")
    files={"height":str(destination/"height.png")}
    try:
        weights=t.texture_weights()
        palette=np.array([[112,111,75],[118,88,56],[78,102,77],[142,143,145],[64,80,89],[113,93,119],[158,143,104],[55,68,78]])
        sumw=weights.sum(axis=0)
        rgb=np.einsum('lhw,lc->hwc',weights.astype(float),palette)/np.maximum(sumw[:,:,None],1)
        texture=Image.fromarray(np.flipud(np.clip(rgb,0,255).astype('u1'))).resize((720,600),Image.Resampling.LANCZOS)
        d=ImageDraw.Draw(texture);d.rectangle((0,0,720,25),fill="#17232c");d.text((8,7),"TEXTURE WEIGHT MAP | diagnostic colors, not actual materials",fill="white")
        texture.save(destination/"textures.png");files["textures"]=str(destination/"textures.png")
    except SC2Error as exc:
        unavailable.append({'preview':'textures',**exc.as_dict()})
    path_view=base.copy();d=ImageDraw.Draw(path_view,"RGBA")
    try:
        mask=t.pathing_layer("CellAttribute_Pnp")
        for y,x in np.argwhere(mask!=0):
            px=x/t.tile_width*720;py=(t.tile_height-y-1)/t.tile_height*600
            d.rectangle((px,py,px+720/t.tile_width,py+600/t.tile_height),fill=(255,55,45,140))
        d.rectangle((0,0,720,25),fill=(23,35,44,255));d.text((8,7),"PAINTED GROUND RESTRICTIONS | excludes footprints/engine pathfinding",fill="white")
        path_view.save(destination/"pathing.png");files["pathing"]=str(destination/"pathing.png")
    except SC2Error as exc:
        unavailable.append({'preview':'pathing',**exc.as_dict()})
    # Orthographic isometric diagnostic; no M3 renderer or material simulation.
    iso=Image.new("RGB",(1000,720),"#17232c");d=ImageDraw.Draw(iso)
    stride=max(1,math.ceil(max(t.width,t.height)/96))
    spacing=min(7,800/(t.width+t.height)*stride)
    def project(x,y,h):
        return (500+(x-y)/stride*spacing,120+(x+y)/stride*spacing*.45-(h-float(z.min()))*7)
    for y in range(0,t.height-stride,stride):
        for x in range(0,t.width-stride,stride):
            points=[project(xx,yy,z[yy,xx]) for xx,yy in [(x,y),(x+stride,y),(x+stride,y+stride),(x,y+stride)]]
            d.polygon(points,fill=tuple(color[y,x]))
    d.text((15,15),"OFFLINE TERRAIN GEOMETRY | no models/materials | not visual acceptance",fill="white")
    iso.save(destination/"terrain-3d.png");files["geometry"]=str(destination/"terrain-3d.png")
    return {"files":files,"source":"offline_component_data","editor_render":False,
            "complete":not unavailable,"unavailable":unavailable,"summary":t.summary()}
