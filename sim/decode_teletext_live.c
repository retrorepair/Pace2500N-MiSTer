// Independent unmodified libzvbi page/subtitle formatting of FPGA output.
#include <libzvbi.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
static void event(vbi_event *e,void *p){(void)e;(void)p;}
int main(int argc,char **argv){
    assert(argc==2);FILE *f=fopen(argv[1],"r");assert(f);
    vbi_decoder *d=vbi_decoder_new();assert(d);
    vbi_event_handler_add(d,VBI_EVENT_TTX_PAGE,event,NULL);
    char line[256];int count=0;
    while(fgets(line,sizeof(line),f)){
        unsigned char b[45];
        for(int i=0;i<45;i++){unsigned x;assert(sscanf(line+2*i,"%2x",&x)==1);b[i]=x;}
        assert(b[0]==0x55 && b[1]==0x55 && b[2]==0x27);
        assert(vbi_unham8(b[3])>=0 && vbi_unham8(b[4])>=0);
        vbi_sliced s={0};s.id=VBI_SLICED_TELETEXT_B;s.line=16;memcpy(s.data,b+3,42);
        vbi_decode(d,&s,1,1.+.04*count++);
    }
    for(int number=0x100;number<=0x888;number+=0x788){
        vbi_page p={0};assert(vbi_fetch_vt_page(d,&p,number,VBI_ANY_SUBNO,VBI_WST_LEVEL_1,25,0));
        char text[25*41+1];int n=0;
        for(int r=0;r<25;r++){for(int c=0;c<40;c++){
            unsigned v=p.text[r*p.columns+c].unicode;text[n++]=v<128?v:'?';
        }text[n++]='\n';}text[n]=0;
        assert(strstr(text,number==0x100 ? "LIVE TRANSPORT PAGE":"SUBTITLE 888 END TO END"));
        if(number==0x888){
            assert(p.text[0].opacity==VBI_TRANSPARENT_SPACE);
            assert(p.text[22*p.columns+10].opacity!=VBI_TRANSPARENT_SPACE);
        }
        printf("PASS libzvbi decoded page %03x%s\n",number,number==0x888 ? " with transparent background and boxed subtitle":"");
        vbi_unref_page(&p);
    }
    vbi_decoder_delete(d);fclose(f);
}
