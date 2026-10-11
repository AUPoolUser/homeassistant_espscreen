#pragma once
// Host-only: the calendar card's real planner (calendar_card.h) and painter (calendar_paint.h) on a board's metrics and
// fonts, for tools/render/calendar_firmware.py. No device firmware includes this file.
#include "esphome/components/lvgl/lvgl_esphome.h"
#include "../../components/smart_display/calendar_paint.h"
#include <cassert>
#include <cstdio>
#include <string>
namespace calfw {
namespace cc = calendar_card;
struct Board {const char *name,*look; int width,height,dpi,cols,rows,top,footer,margin,gx,gy,circle; calendar_paint::Faces f;};
inline cc::Measure measure(const Board &b){
  cc::Measure m;for(int i=0;i<cc::FACES;++i)m.line[i]=b.f[i]?lv_font_get_line_height(b.f[i]):0;
  auto faces=b.f;m.width=[faces](cc::Face f,const std::string &s){if(!faces[f])return 1<<20;lv_point_t p;lv_text_get_size(&p,s.c_str(),faces[f],0,0,LV_COORD_MAX,LV_TEXT_FLAG_NONE);return (int)p.x;};
  m.circle=b.circle;return m;
}
inline cc::Words words(){
  cc::Words w;w.free="Free";w.busy="Busy";w.starts_soon="Starts soon";w.private_title="Busy";w.all_day="All day";w.today="Today";w.tomorrow="Tomorrow";
  w.nothing="Nothing planned";w.nothing_more="Nothing else this week";w.until="Until {x}";w.next="Next {x}";w.left="{x} left";w.in="in {x}";
  w.more="{x} more";w.earlier="{x} earlier";w.later="{x} later";w.week="Week {x}";w.more_week="{x} more this week";
  w.days={"Mon","Tue","Wed","Thu","Fri","Sat","Sun"};w.days_long={"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"};w.letters={"M","T","W","T","F","S","S"};
  w.months={"January","February","March","April","May","June","July","August","September","October","November","December"};
  w.months_short={"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
  w.views={"Up next","Day","Week","Month"};w.view_notes={"What runs now, then the next ones","One day, a tap on the strip picks it","Days side by side, hours down","A glance at the month, a tap opens a day"};
  w.today_key="Today";w.clock=[](int m){char b[8];snprintf(b,sizeof b,"%02d:%02d",m/60%24,m%60);return std::string(b);};return w;
}
// Wednesday 14 October 2026; three calendars in Home Assistant's first palette colours.
inline cc::Data demo(){
  cc::Data d;d.year=2026;d.month=10;d.day=14;d.weekday=2;d.colors={0x4269D0,0xF4BD4A,0xFF725C};d.names={"Home","Work","School"};d.from=-2;d.to=14;
  auto H=[](int h,int m=0){return h*60+m;};
  auto ev=[&](int day,int a,int b,const char *t,uint8_t c,uint8_t f=0,const char *pl=""){cc::Event e;e.start=day*1440+a;e.end=day*1440+b;e.title=t;e.cal=c;e.flags=f;e.place=pl;d.events.push_back(e);};
  ev(-2,0,5*1440,"Sprint week",1,cc::ALL_DAY);
  ev(-2,H(10),H(10,30),"Kick-off call",1);ev(-2,H(19),H(21,30),"Choir rehearsal",0);
  ev(-1,H(9),H(10),"Dentist",0,0,"Main Street 12");ev(-1,H(13),H(16),"Workshop",1);
  ev(0,H(8,15),H(8,45),"School run",0);ev(0,H(11),H(12),"Sign the lease",0);ev(0,H(13,30),H(15),"Design review",1,0,"Room 2");
  ev(0,H(15,30),H(16),"Parent evening",2);ev(0,H(17),H(18),"Presentation",1);ev(0,H(19),H(22),"Dinner with friends",0,0,"De Kas");
  ev(1,0,1440,"Bin day",0,cc::ALL_DAY);ev(1,H(9),H(9,45),"Drop off the car",0);ev(1,H(10),H(10,30),"Admin",1);ev(1,H(14),H(15,30),"Library",2);
  ev(2,H(10,30),H(12),"Contracts",1);ev(2,H(11),H(11,30),"Coffee with Ana",0,cc::TENTATIVE);ev(2,H(12),H(13),"Send invoices",1);ev(2,H(14),H(15),"Retainer review",1);
  ev(3,0,1440,"Grandma's birthday",0,cc::ALL_DAY);ev(3,H(10),H(11),"Football practice",0);ev(4,H(10),H(12),"Farmers market",0);
  ev(6,H(9),H(10),"Dentist",0);ev(8,H(19),H(21),"Parent evening",2);ev(9,H(10),H(11),"Board meeting",1);
  std::stable_sort(d.events.begin(),d.events.end(),[](auto &a,auto &b){return a.start<b.start;});
  d.notes="Walk through the new onboarding screens and agree on the copy.";
  d.glance_from=-16;for(int i=0;i<42;++i){int day=-16+i;uint8_t m=0;if(day<d.from||day>d.to)m=(i%3?1:0)|(i%4==1?2:0)|(i%7==3?4:0);d.glance.push_back(m);}
  return d;
}
struct Drawn {cc::Scene *sc=nullptr;const std::vector<uint32_t> *colors=nullptr;calendar_paint::Faces faces{};int ox=0,oy=0;};
inline void draw_cb(lv_event_t *e){
  auto *o=static_cast<lv_obj_t*>(lv_event_get_current_target(e));auto *d=static_cast<Drawn*>(lv_obj_get_user_data(o));if(!d)return;
  lv_area_t a;lv_obj_get_coords(o,&a);calendar_paint::paint(lv_event_get_layer(e),*d->sc,a.x1+d->ox,a.y1+d->oy,d->faces,*d->colors);
}
inline lv_obj_t *box(lv_obj_t *p,int x,int y,int w,int h,uint32_t c,int r=0){auto *o=lv_obj_create(p);lv_obj_remove_style_all(o);lv_obj_remove_flag(o,LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_pos(o,x,y);lv_obj_set_size(o,w,h);lv_obj_set_style_bg_color(o,lv_color_hex(c),0);lv_obj_set_style_bg_opa(o,LV_OPA_COVER,0);lv_obj_set_style_radius(o,r,0);return o;}
inline lv_obj_t *canvas(lv_obj_t *p,int x,int y,int w,int h,Drawn *d){auto *o=lv_obj_create(p);lv_obj_remove_style_all(o);lv_obj_remove_flag(o,LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_pos(o,x,y);lv_obj_set_size(o,w,h);lv_obj_set_user_data(o,d);lv_obj_add_event_cb(o,draw_cb,LV_EVENT_DRAW_MAIN,nullptr);return o;}
inline void save(lv_obj_t *root,const std::string &path){
  lv_obj_update_layout(root);auto *buf=lv_snapshot_take(root,LV_COLOR_FORMAT_RGB888);assert(buf);
  FILE *fp=fopen(path.c_str(),"wb");assert(fp);fprintf(fp,"P6\n%d %d\n255\n",int(buf->header.w),int(buf->header.h));
  for(int y=0;y<int(buf->header.h);++y)for(int x=0;x<int(buf->header.w);++x){const auto *q=buf->data+y*buf->header.stride+3*x;uint8_t rgb[]={q[2],q[1],q[0]};fwrite(rgb,1,3,fp);}
  fclose(fp);lv_draw_buf_destroy(buf);
}
// mode 0: a card of c x r cells on a page; 1..: the full screen in a view (1 up next, 2 day, 3 week, 4 month), +10 with the
// view key's choice open, +20 with an event's sheet.
inline void render(const Board &b,const std::string &out,const std::string &file,int c,int rr,int minute,bool dark,int mode,cc::Options o=cc::Options{}){
  mode%=100;
  ui::configure(b.dpi,b.look);theme::set_dark(dark);
  static cc::Data d=demo();static cc::Words w=words();
  const cc::Measure m=measure(b);const cc::Moment t{0,minute};
  auto *root=box(lv_screen_active(),0,0,b.width,b.height,theme::hex(theme::PAGE));
  static cc::Scene s1,s2,s3;static cc::Full full;static Drawn d1,d2,d3;
  const char *view="";
  if(mode==0){
    const int cw=(b.width-2*b.margin-(b.cols-1)*b.gx)/b.cols,ch=(b.height-b.top-b.footer-(b.rows-1)*b.gy)/b.rows;
    for(int row=0;row<b.rows;++row)for(int col=0;col<b.cols;++col){if(row<rr&&col<c)continue;
      auto *n=box(root,b.margin+col*(cw+b.gx),b.top+row*(ch+b.gy),cw,ch,theme::hex(theme::CARD),ui::px(ui::large()?22:18));lv_obj_set_style_border_width(n,1,0);lv_obj_set_style_border_color(n,theme::color(theme::LINE),0);}
    const int W=c*cw+(c-1)*b.gx,Hh=rr*ch+(rr-1)*b.gy;
    auto *card=box(root,b.margin,b.top,W,Hh,theme::hex(theme::CARD),ui::px(ui::large()?22:18));lv_obj_set_style_border_width(card,1,0);lv_obj_set_style_border_color(card,theme::color(theme::LINE),0);
    const int pad=ui::px(ui::large()?14:8),radius=ui::px(ui::large()?22:18);
    const cc::View v=cc::plan_tile(s1,m,W-2*pad,Hh-2*pad,d,t,o,w,"Family",cc::Edge{pad,pad,pad,pad,radius});
    static const char *names[]={"now","up-next","agenda","columns","week","day","blocks","month"};view=names[v];
    d1={&s1,&d.colors,b.f,pad,pad};canvas(card,-1,-1,W,Hh,&d1);
  }else{
    cc::State st;const int base=mode%10;st.view=base==1?cc::UP_NEXT:base==2?cc::DAY:base==3?cc::WEEK:cc::MONTH;st.day=base==4?2:0;st.menu=mode>=10&&mode<20;
    if(mode>=20){for(size_t i=0;i<d.events.size();++i)if(d.events[i].title=="Design review")st.sheet=(int)i;}
    auto *page=box(root,0,0,b.width,b.height,theme::hex(theme::CARD));
    const cc::View v=cc::plan_full(full,m,b.width,b.height,b.margin,d,t,o,w,"Family",st);
    static const char *names[]={"now","up-next","agenda","columns","week","day","blocks","month"};view=names[v];
    d1={&full.fixed,&d.colors,b.f,0,0};canvas(page,0,0,b.width,b.height,&d1);
    if(full.sh>0){d2={&full.scroll,&d.colors,b.f,0,-full.scroll_to};auto *sc=canvas(page,full.sx,full.sy,full.sw,full.sh,&d2);(void)sc;}
    d3={&full.overlay,&d.colors,b.f,0,0};canvas(page,0,0,b.width,b.height,&d3);
  }
  printf("VIEW %s %s\n",file.c_str(),view);fflush(stdout);
  save(root,out+"/"+file+".ppm");lv_obj_delete(root);
}
}  // namespace calfw
