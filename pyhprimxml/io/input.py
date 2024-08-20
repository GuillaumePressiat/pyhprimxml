import xmltodict
import polars as pl
import io
import lxml.etree as ET
import os
import json

def remove_namespaces(doc):
    # http://wiki.tei-c.org/index.php/Remove-Namespaces.xsl
    xslt='''<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="no"/>

    <xsl:template match="/|comment()|processing-instruction()">
        <xsl:copy>
          <xsl:apply-templates/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="*">
        <xsl:element name="{local-name()}">
          <xsl:apply-templates select="@*|node()"/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="@*">
        <xsl:attribute name="{local-name()}">
          <xsl:value-of select="."/>
        </xsl:attribute>
    </xsl:template>
    </xsl:stylesheet>
    '''

    xslt_doc = ET.parse(io.StringIO(xslt))
    transform = ET.XSLT(xslt_doc)
    doc = transform(doc)
    return doc

def read_hprimxml(f):
    
    #tree = xmltodict.parse(open(f, 'r').read())
    tree = ET.parse(f)
    tree =  remove_namespaces(tree)

    tree = xmltodict.parse(tree, attr_prefix="", force_list = ('actes'))

    # On fixe ici la structure xml qui ne distingue pas entre Struct et List(Struct)
    # si 1 seul acte le json > struct { ... }
    # si >1 actes le json > list(struct) [ {...}, {...}, ...]

    # if 'evenementsPMSI' in tree.keys():
    #     try:
    #         temp = tree['evenementsPMSI']['evenementPMSI']['rss']['rum']
        
    #         for i in range(len(temp)):
    #             #print(type(temp[i]['actes']['acte']))
    #             #print(temp[i]['actes']['acte'])
    #             if type(temp[i]['actes']['acte']) == dict:
    #                 #print('nok')
    #                 temp[i]['actes']['acte'] = [temp[i]['actes']['acte']]
        
    #         tree['evenementsPMSI']['evenementPMSI']['rss']['rum'] = temp
            
    #     except:
    #         True

    short_f = os.path.basename(f)
    content = pl.read_json(io.StringIO(json.dumps(tree)))
    #content = pl.DataFrame(xmltodict.parse(tree))


    
    r = dict(type_evenement = content.columns,
             message = (content
                        .unnest(content.columns)
                 .with_columns(pl.lit(short_f).alias('source_id'))
             )
            )

    return r


