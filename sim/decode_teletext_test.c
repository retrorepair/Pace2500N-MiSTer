// Independent page decoding using Ubuntu's unmodified libzvbi.
#include <libzvbi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static void event(vbi_event *ev,void *opaque){(void)ev;(void)opaque;}
int main(int argc,char **argv){
    assert(argc==2);
    FILE *f=fopen(argv[1],"r");assert(f);
    vbi_decoder *d=vbi_decoder_new();assert(d);
    vbi_event_handler_add(d,VBI_EVENT_TTX_PAGE,event,NULL);
    char line[256];int count=0;vbi_sliced frame[2]={{0}};
    while(fgets(line,sizeof(line),f)){
        unsigned char packet[45];
        for(int i=0;i<45;i++){unsigned b;assert(sscanf(line+i*2,"%2x",&b)==1);packet[i]=b;}
        assert(packet[0]==0x55 && packet[1]==0x55 && packet[2]==0x27);
        int a=vbi_unham8(packet[3]),b=vbi_unham8(packet[4]);
        assert(a>=0 && b>=0 && (a&7)==1);
        int row=((a>>3)&1)|(b<<1);
        assert(row==count%25);
        if(!row){assert(vbi_unham8(packet[5])==0 && vbi_unham8(packet[6])==0);}
        for(int i=row ? 5:13;i<45;i++)assert(vbi_unpar8(packet[i])>=0);
        vbi_sliced s={0};s.id=VBI_SLICED_TELETEXT_B;s.line=count%2 ? 329:16;
        memcpy(s.data,packet+3,42);
        frame[count%2]=s;
        // libzvbi consumes complete 25 Hz frames, not separate 50 Hz fields.
        if(count%2)vbi_decode(d,frame,2,1.+(count/2)*.040);
        count++;
    }
    // Repeated erase-page headers publish the previous complete carousel.
    // Do not flush the final partial carousel over that cached complete page.
    vbi_page page={0};
    assert(count>=26);
    assert(vbi_fetch_vt_page(d,&page,0x100,VBI_ANY_SUBNO,VBI_WST_LEVEL_1,25,0));
    char text[25][41];
    for(int r=0;r<25;r++){
        for(int c=0;c<40;c++){unsigned ch=page.text[r*page.columns+c].unicode;text[r][c]=ch<128 ? ch:'?';}
        text[r][40]=0;puts(text[r]);
    }
    assert(strstr(text[4],"PAGE 100 - HSync PDM experiment"));
    assert(strstr(text[7],"Your TV decoded the VBI test signal."));
    assert(strstr(text[24],"PACE TEST 100"));
    printf("PASS libzvbi decoded FPGA physical-output fixture: page %03x, %d packets\n",page.pgno,count);
    vbi_unref_page(&page);vbi_decoder_delete(d);fclose(f);
}
